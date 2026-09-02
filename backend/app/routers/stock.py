from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_module

router = APIRouter(prefix="/api/stock", tags=["stock"], dependencies=[Depends(require_module("stock"))])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    type: models.StockMovementType
    quantite: int
    motif: str | None = None
    created_at: object


@router.get("/alertes", response_model=list[schemas.ProductOut])
def stock_alerts(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return (
        db.query(models.Product)
        .filter(models.Product.shop_id == shop.id, models.Product.stock <= models.Product.seuil_alerte)
        .order_by(models.Product.stock)
        .all()
    )


def _sales_by_product(db: Session, shop_id: int, since: datetime) -> dict[int, tuple[int, float]]:
    """{product_id: (quantité vendue, chiffre d'affaires)} depuis `since`, commandes
    non annulées/échouées uniquement."""
    rows = (
        db.query(
            models.OrderItem.product_id,
            func.sum(models.OrderItem.quantite).label("qte"),
            func.sum(models.OrderItem.quantite * models.OrderItem.prix_unitaire).label("ca"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.Order.shop_id == shop_id,
            models.Order.created_at >= since,
            ~models.Order.statut.in_(CANCELLED_STATUSES),
        )
        .group_by(models.OrderItem.product_id)
        .all()
    )
    return {r.product_id: (int(r.qte or 0), float(r.ca or 0)) for r in rows}


@router.get("/statistiques", response_model=schemas.StockStatsOut)
def stock_statistics(
    jours_ventes: int = 30,
    jours_dormant: int = 60,
    limite: int = 10,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    products = db.query(models.Product).filter(models.Product.shop_id == shop.id, models.Product.actif.is_(True)).all()

    valeur_stock_achat = sum(p.stock * p.prix_achat for p in products)
    valeur_stock_vente = sum(p.stock * p.prix_vente for p in products)

    ventes_recentes = _sales_by_product(db, shop.id, datetime.utcnow() - timedelta(days=jours_ventes))
    ventes_dormant = _sales_by_product(db, shop.id, datetime.utcnow() - timedelta(days=jours_dormant))

    def to_stat(p: models.Product, qte: int, ca: float) -> schemas.ProductSalesStat:
        return schemas.ProductSalesStat(
            product_id=p.id, nom=p.nom, stock=p.stock, quantite_vendue=qte,
            chiffre_affaires=ca, valeur_stock=p.stock * p.prix_achat,
        )

    avec_ventes = [(p, *ventes_recentes[p.id]) for p in products if p.id in ventes_recentes]
    plus_vendus = sorted(avec_ventes, key=lambda t: t[1], reverse=True)[:limite]
    moins_vendus = sorted(avec_ventes, key=lambda t: t[1])[:limite]

    stock_dormant = [
        p for p in products
        if p.stock > 0 and ventes_dormant.get(p.id, (0, 0))[0] == 0
    ]
    stock_dormant.sort(key=lambda p: p.stock * p.prix_achat, reverse=True)

    quantite_totale_vendue = sum(qte for qte, _ in ventes_recentes.values())
    stock_total_actuel = sum(p.stock for p in products)
    rotation_globale = (quantite_totale_vendue / stock_total_actuel) if stock_total_actuel > 0 else None

    return schemas.StockStatsOut(
        valeur_stock_achat=valeur_stock_achat,
        valeur_stock_vente=valeur_stock_vente,
        benefice_potentiel=valeur_stock_vente - valeur_stock_achat,
        rotation_globale=rotation_globale,
        produits_plus_vendus=[to_stat(p, qte, ca) for p, qte, ca in plus_vendus],
        produits_moins_vendus=[to_stat(p, qte, ca) for p, qte, ca in moins_vendus],
        stock_dormant=[to_stat(p, *ventes_dormant.get(p.id, (0, 0))) for p in stock_dormant[:limite]],
    )


@router.post("/{product_id}/ajuster", response_model=schemas.ProductOut)
def adjust_stock(
    product_id: int,
    payload: schemas.StockAdjustIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")

    new_stock = product.stock + payload.quantite
    if new_stock < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le stock ne peut pas être négatif")

    product.stock = new_stock
    movement_type = models.StockMovementType.REAPPRO if payload.quantite > 0 else models.StockMovementType.AJUSTEMENT
    db.add(models.StockMovement(
        product_id=product.id,
        type=movement_type,
        quantite=payload.quantite,
        motif=payload.motif,
    ))
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/mouvements", response_model=list[StockMovementOut])
def stock_movements(
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")

    return (
        db.query(models.StockMovement)
        .filter(models.StockMovement.product_id == product_id)
        .order_by(models.StockMovement.created_at.desc())
        .all()
    )
