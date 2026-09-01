import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/api/abonnement", tags=["abonnement"])


@router.get("/wave-qr.png")
def subscription_wave_qr(
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """QR de paiement d'abonnement plateforme (pas celui d'une boutique) —
    accessible à tout compte connecté (propriétaire, employé, admin) puisqu'il
    n'est pas rattaché à une boutique en particulier."""
    settings_row = db.get(models.PlatformSettings, 1)
    if settings_row is None or not settings_row.wave_payment_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun lien de paiement d'abonnement configuré",
        )
    img = qrcode.make(settings_row.wave_payment_link)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")
