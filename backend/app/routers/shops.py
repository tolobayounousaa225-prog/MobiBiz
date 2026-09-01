import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
