from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _get_owned_category(db: Session, shop: models.Shop, category_id: int) -> models.Category:
    category = (
        db.query(models.Category)
        .filter(models.Category.id == category_id, models.Category.shop_id == shop.id)
        .first()
    )
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable")
    return category


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return db.query(models.Category).filter(models.Category.shop_id == shop.id).order_by(models.Category.nom).all()


@router.post("", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: schemas.CategoryIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    category = models.Category(shop_id=shop.id, nom=payload.nom)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int,
    payload: schemas.CategoryIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    category = _get_owned_category(db, shop, category_id)
    category.nom = payload.nom
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    category = _get_owned_category(db, shop, category_id)
    db.delete(category)
    db.commit()
