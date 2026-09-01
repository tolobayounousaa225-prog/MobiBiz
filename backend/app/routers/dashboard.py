from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


@router.get("", response_model=schemas.DashboardOut)
def get_dashboard(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    orders = (
        db.query(models.Order)
        .filter(models.Order.shop_id == shop.id, ~models.Order.statut.in_(CANCELLED_STATUSES))
        .all()
    )
    chiffre_affaires = sum(o.total for o in orders)
    impayes = sum(o.total for o in orders if o.paiement_statut != models.PaiementStatut.PAYE)

    benefice_estime = 0.0
    for order in orders:
        for item in order.items:
            benefice_estime += (item.prix_unitaire - item.prix_achat_unitaire) * item.quantite

    nombre_clients = db.query(models.Customer).filter(models.Customer.shop_id == shop.id).count()
    nombre_produits = db.query(models.Product).filter(models.Product.shop_id == shop.id).count()
    produits_stock_faible = (
        db.query(models.Product)
        .filter(models.Product.shop_id == shop.id, models.Product.stock <= models.Product.seuil_alerte)
        .count()
    )

    return schemas.DashboardOut(
        chiffre_affaires=chiffre_affaires,
        nombre_commandes=len(orders),
        nombre_clients=nombre_clients,
        nombre_produits=nombre_produits,
        benefice_estime=benefice_estime,
        impayes=impayes,
        produits_stock_faible=produits_stock_faible,
    )
