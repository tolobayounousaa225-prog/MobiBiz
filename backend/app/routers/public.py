from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..notifications import notify
from ..rate_limit import enforce_public_order_rate_limit
from .orders import _generate_order_number

router = APIRouter(prefix="/api/public/boutiques", tags=["boutique-publique"])


def _get_active_public_shop(db: Session, slug: str) -> models.Shop:
    shop = (
        db.query(models.Shop)
        .filter(models.Shop.slug == slug, models.Shop.boutique_publique_active.is_(True))
        .first()
    )
    if shop is None or shop.abonnement_statut == models.SubscriptionStatus.SUSPENDU:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boutique introuvable")
    return shop


@router.get("/{slug}", response_model=schemas.PublicShopOut)
def get_public_shop(slug: str, db: Session = Depends(get_db)):
    shop = _get_active_public_shop(db, slug)
    products = (
        db.query(models.Product)
        .filter(models.Product.shop_id == shop.id, models.Product.actif.is_(True), models.Product.stock > 0)
        .order_by(models.Product.nom)
        .all()
    )
    categories = db.query(models.Category).filter(models.Category.shop_id == shop.id).order_by(models.Category.nom).all()
    return schemas.PublicShopOut(
        nom=shop.nom,
        description=shop.description,
        telephone=shop.telephone,
        whatsapp=shop.whatsapp,
        adresse=shop.adresse,
        commune=shop.commune,
        logo_url=shop.logo_url,
        produits=products,
        categories=categories,
    )


@router.post("/{slug}/commandes", response_model=schemas.PublicOrderOut, status_code=status.HTTP_201_CREATED)
def create_public_order(slug: str, payload: schemas.PublicOrderIn, request: Request, db: Session = Depends(get_db)):
    enforce_public_order_rate_limit(request)
    shop = _get_active_public_shop(db, slug)

    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La commande doit contenir au moins un produit")

    customer = (
        db.query(models.Customer)
        .filter(models.Customer.shop_id == shop.id, models.Customer.telephone == payload.client_telephone)
        .first()
    )
    if customer is None:
        customer = models.Customer(
            shop_id=shop.id,
            nom=payload.client_nom,
            telephone=payload.client_telephone,
            commune=payload.client_commune,
        )
        db.add(customer)
        db.flush()

    order = models.Order(
        shop_id=shop.id,
        customer_id=customer.id,
        numero=_generate_order_number(db, shop.id),
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    sous_total = 0.0
    for item in payload.items:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id, models.Product.shop_id == shop.id, models.Product.actif.is_(True))
            .first()
        )
        if product is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Produit {item.product_id} invalide")
        if product.stock < item.quantite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuffisant pour « {product.nom} » (disponible : {product.stock})",
            )

        stock_avant = product.stock
        product.stock -= item.quantite
        db.add(models.StockMovement(product_id=product.id, type=models.StockMovementType.VENTE, quantite=-item.quantite))
        if product.stock <= product.seuil_alerte < stock_avant:
            notify(db, shop.id, models.NotificationType.STOCK_FAIBLE, f"Stock faible : « {product.nom} » (reste {product.stock})")

        db.add(models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantite=item.quantite,
            prix_unitaire=product.effective_price,
            prix_achat_unitaire=product.prix_achat,
        ))
        sous_total += product.effective_price * item.quantite

    order.total = sous_total
    notify(
        db, shop.id, models.NotificationType.NOUVELLE_COMMANDE,
        f"Nouvelle commande {order.numero} de {customer.nom} (boutique publique) — {order.total:.0f} FCFA",
        order_id=order.id,
    )
    db.commit()

    return schemas.PublicOrderOut(numero=order.numero, total=order.total)
