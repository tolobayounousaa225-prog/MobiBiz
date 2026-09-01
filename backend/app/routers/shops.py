from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/boutique", tags=["boutique"])


@router.get("", response_model=schemas.ShopOut)
def get_shop(shop: models.Shop = Depends(get_current_shop)):
    return shop


@router.put("", response_model=schemas.ShopOut)
def update_shop(
    payload: schemas.ShopIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    for field, value in payload.model_dump().items():
        setattr(shop, field, value)
    db.commit()
    db.refresh(shop)
    return shop
