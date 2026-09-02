import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db
from ..deps import get_current_shop, require_owner
from ..plans import plan_limit

router = APIRouter(prefix="/api/boutique", tags=["boutique"])


@router.get("", response_model=schemas.ShopOut)
def get_shop(shop: models.Shop = Depends(get_current_shop)):
    return shop


@router.put("", response_model=schemas.ShopOut)
def update_shop(
    payload: schemas.ShopIn,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    if payload.boutique_publique_active and not plan_limit(shop.abonnement_plan, "boutique_publique"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La boutique publique n'est pas disponible sur votre plan actuel. Passez à un plan supérieur pour l'activer.",
        )
    for field, value in payload.model_dump().items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop


@router.put("/abonnement", response_model=schemas.ShopOut)
def change_plan(
    payload: schemas.ShopPlanChangeIn,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Souscription en libre-service : le propriétaire choisit lui-même son plan
    (immédiat, sans validation admin). Le paiement reste suivi séparément
    (QR Wave + enregistrement admin) — un plan choisi mais non payé finira par
    apparaître en retard de paiement dans le tableau de bord admin."""
    shop.abonnement_plan = payload.abonnement_plan
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/actions-en-attente", response_model=schemas.PendingActionsOut)
def pending_actions(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    """Compte les éléments nécessitant une action du gestionnaire, affichés en
    badge directement sur les onglets concernés de la barre latérale — évite de
    devoir ouvrir chaque section pour savoir s'il y a quelque chose à faire.
    Le frontend décide seul quel badge afficher selon les modules accessibles à
    l'utilisateur connecté (employé ou propriétaire) ; ici on renvoie tout."""
    commandes = (
        db.query(models.Order)
        .filter(models.Order.shop_id == shop.id, models.Order.statut == models.OrderStatus.NOUVELLE)
        .count()
    )
    stock = (
        db.query(models.Product)
        .filter(
            models.Product.shop_id == shop.id, models.Product.actif.is_(True),
            models.Product.stock <= models.Product.seuil_alerte,
        )
        .count()
    )
    avis = (
        db.query(models.ProductReview)
        .filter(models.ProductReview.shop_id == shop.id, models.ProductReview.approuve.is_(False))
        .count()
    )
    return schemas.PendingActionsOut(commandes=commandes, stock=stock, avis=avis)


@router.get("/{shop_id}/logo")
def get_shop_logo(shop_id: int, db: Session = Depends(get_db)):
    """Public (pas d'authentification) — affiché sur la boutique publique et dans
    l'espace propriétaire, même logique que la photo produit."""
    shop = db.get(models.Shop, shop_id)
    if shop is None or not shop.logo_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo introuvable")
    stored = storage.get_stored_file(db, shop.logo_path)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)


@router.post("/logo", response_model=schemas.ShopOut)
async def upload_shop_logo(
    file: UploadFile,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    try:
        path = await storage.save_upload(db, file, "boutiques", storage.ALLOWED_PHOTO_EXT)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    storage.delete_stored_file(db, shop.logo_path)
    shop.logo_path = path
    db.commit()
    db.refresh(shop)
    return shop


@router.delete("/logo", response_model=schemas.ShopOut)
def remove_shop_logo(
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    storage.delete_stored_file(db, shop.logo_path)
    shop.logo_path = None
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/paiements", response_model=list[schemas.SubscriptionPaymentOut])
def list_my_subscription_payments(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return (
        db.query(models.SubscriptionPayment)
        .filter(models.SubscriptionPayment.shop_id == shop.id)
        .order_by(models.SubscriptionPayment.date_paiement.desc())
        .all()
    )


@router.get("/paiements/{payment_id}/recu.pdf")
def download_payment_receipt(
    payment_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(models.SubscriptionPayment)
        .filter(models.SubscriptionPayment.id == payment_id, models.SubscriptionPayment.shop_id == shop.id)
        .first()
    )
    if payment is None or not payment.recu_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reçu introuvable")
    stored = storage.get_stored_file(db, payment.recu_path)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reçu introuvable")
    return Response(
        content=stored.data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recu-{payment.date_paiement}.pdf"'},
    )


@router.get("/wave-qr.png")
def wave_qr_code(shop: models.Shop = Depends(get_current_shop)):
    if not shop.wave_payment_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun lien de paiement Wave configuré pour cette boutique",
        )

    img = qrcode.make(shop.wave_payment_link)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
