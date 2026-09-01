import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
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
