from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/produits", tags=["produits"])


def _get_owned_product(db: Session, shop: models.Shop, product_id: int) -> models.Product:
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")
    return product


@router.get("", response_model=list[schemas.ProductOut])
def list_products(
    q: str | None = None,
    category_id: int | None = None,
    stock_faible: bool = False,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    query = db.query(models.Product).filter(models.Product.shop_id == shop.id)
    if q:
        query = query.filter(models.Product.nom.ilike(f"%{q}%"))
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if stock_faible:
        query = query.filter(models.Product.stock <= models.Product.seuil_alerte)
    return query.order_by(models.Product.nom).all()


@router.post("", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: schemas.ProductIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    if payload.category_id is not None:
        category = (
            db.query(models.Category)
            .filter(models.Category.id == payload.category_id, models.Category.shop_id == shop.id)
            .first()
        )
        if category is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Catégorie invalide")

    product = models.Product(shop_id=shop.id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return _get_owned_product(db, shop, product_id)


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    payload: schemas.ProductIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, shop, product_id)
    for field, value in payload.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    product = _get_owned_product(db, shop, product_id)
    db.delete(product)
    db.commit()
