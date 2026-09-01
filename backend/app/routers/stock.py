from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_module

router = APIRouter(prefix="/api/stock", tags=["stock"], dependencies=[Depends(require_module("stock"))])


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
