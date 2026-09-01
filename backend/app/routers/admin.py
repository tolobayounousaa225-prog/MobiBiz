from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_admin

PAYMENT_VALIDITY_DAYS = 30

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


def _shop_to_admin_out(db: Session, shop: models.Shop) -> schemas.AdminShopOut:
    orders = (
        db.query(models.Order)
        .filter(models.Order.shop_id == shop.id, ~models.Order.statut.in_(CANCELLED_STATUSES))
        .all()
    )
    nombre_produits = db.query(models.Product).filter(models.Product.shop_id == shop.id).count()
    return schemas.AdminShopOut(
        id=shop.id,
        nom=shop.nom,
        slug=shop.slug,
        abonnement_statut=shop.abonnement_statut,
        abonnement_plan=shop.abonnement_plan,
        prochain_paiement_le=shop.prochain_paiement_le.isoformat() if shop.prochain_paiement_le else None,
        proprietaire_nom=f"{shop.owner.prenom} {shop.owner.nom}",
        proprietaire_telephone=shop.owner.telephone,
        nombre_produits=nombre_produits,
        nombre_commandes=len(orders),
        chiffre_affaires=sum(o.total for o in orders),
        created_at=shop.created_at,
    )


def _get_shop_or_404(db: Session, shop_id: int) -> models.Shop:
    shop = db.get(models.Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boutique introuvable")
    return shop


@router.get("/boutiques", response_model=list[schemas.AdminShopOut])
def list_shops(db: Session = Depends(get_db)):
    shops = db.query(models.Shop).order_by(models.Shop.created_at.desc()).all()
    return [_shop_to_admin_out(db, shop) for shop in shops]


@router.get("/boutiques/{shop_id}", response_model=schemas.AdminShopOut)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    return _shop_to_admin_out(db, _get_shop_or_404(db, shop_id))


@router.patch("/boutiques/{shop_id}/statut", response_model=schemas.AdminShopOut)
def update_shop_status(shop_id: int, payload: schemas.AdminShopStatusIn, db: Session = Depends(get_db)):
    shop = _get_shop_or_404(db, shop_id)
    shop.abonnement_statut = payload.abonnement_statut
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


@router.patch("/boutiques/{shop_id}/abonnement", response_model=schemas.AdminShopOut)
def update_shop_plan(shop_id: int, payload: schemas.AdminShopPlanIn, db: Session = Depends(get_db)):
    shop = _get_shop_or_404(db, shop_id)
    shop.abonnement_plan = payload.abonnement_plan
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


@router.get("/utilisateurs", response_model=list[schemas.AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    result = []
    for user in users:
        boutique_nom = None
        if user.role == models.UserRole.OWNER:
            shop = db.query(models.Shop).filter(models.Shop.owner_id == user.id).first()
            boutique_nom = shop.nom if shop else None
        elif user.role == models.UserRole.EMPLOYEE and user.shop_id:
            shop = db.get(models.Shop, user.shop_id)
            boutique_nom = shop.nom if shop else None
        result.append(schemas.AdminUserOut(
            id=user.id, nom=user.nom, prenom=user.prenom, telephone=user.telephone,
            role=user.role, employee_role=user.employee_role, actif=user.actif,
            boutique_nom=boutique_nom, created_at=user.created_at,
        ))
    return result


@router.get("/statistiques", response_model=schemas.AdminStatsOut)
def get_statistics(db: Session = Depends(get_db)):
    shops = db.query(models.Shop).all()
    orders = db.query(models.Order).filter(~models.Order.statut.in_(CANCELLED_STATUSES)).all()

    return schemas.AdminStatsOut(
        boutiques_total=len(shops),
        boutiques_actives=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.ACTIF),
        boutiques_suspendues=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.SUSPENDU),
        boutiques_essai=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.ESSAI),
        utilisateurs_total=db.query(models.User).filter(models.User.role != models.UserRole.ADMIN).count(),
        commandes_total=len(orders),
        chiffre_affaires_total=sum(o.total for o in orders),
    )


@router.get("/boutiques/{shop_id}/paiements", response_model=list[schemas.SubscriptionPaymentOut])
def list_shop_payments(shop_id: int, db: Session = Depends(get_db)):
    _get_shop_or_404(db, shop_id)
    return (
        db.query(models.SubscriptionPayment)
        .filter(models.SubscriptionPayment.shop_id == shop_id)
        .order_by(models.SubscriptionPayment.date_paiement.desc())
        .all()
    )


@router.post("/boutiques/{shop_id}/paiements", response_model=schemas.AdminShopOut, status_code=status.HTTP_201_CREATED)
def record_shop_payment(shop_id: int, payload: schemas.SubscriptionPaymentIn, db: Session = Depends(get_db)):
    shop = _get_shop_or_404(db, shop_id)
    try:
        parsed_date = date_type.fromisoformat(payload.date_paiement)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format attendu AAAA-MM-JJ)")

    db.add(models.SubscriptionPayment(shop_id=shop.id, montant=payload.montant, date_paiement=parsed_date))
    shop.prochain_paiement_le = parsed_date + timedelta(days=PAYMENT_VALIDITY_DAYS)
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


def _get_or_create_platform_settings(db: Session) -> models.PlatformSettings:
    settings_row = db.get(models.PlatformSettings, 1)
    if settings_row is None:
        settings_row = models.PlatformSettings(id=1)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


@router.get("/parametres", response_model=schemas.PlatformSettingsOut)
def get_platform_settings(db: Session = Depends(get_db)):
    return _get_or_create_platform_settings(db)


@router.put("/parametres", response_model=schemas.PlatformSettingsOut)
def update_platform_settings(payload: schemas.PlatformSettingsIn, db: Session = Depends(get_db)):
    settings_row = _get_or_create_platform_settings(db)
    settings_row.wave_payment_link = payload.wave_payment_link
    db.commit()
    db.refresh(settings_row)
    return settings_row
