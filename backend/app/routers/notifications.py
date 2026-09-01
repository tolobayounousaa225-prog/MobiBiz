from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    limit: int = 30,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.shop_id == shop.id)
        .order_by(models.Notification.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )


@router.get("/non-lues/compte")
def unread_count(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    count = (
        db.query(models.Notification)
        .filter(models.Notification.shop_id == shop.id, models.Notification.lu.is_(False))
        .count()
    )
    return {"compte": count}


@router.patch("/lu-tout", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    db.query(models.Notification).filter(
        models.Notification.shop_id == shop.id, models.Notification.lu.is_(False)
    ).update({"lu": True})
    db.commit()


@router.patch("/{notification_id}/lu", response_model=schemas.NotificationOut)
def mark_read(
    notification_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id, models.Notification.shop_id == shop.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification introuvable")
    notification.lu = True
    db.commit()
    db.refresh(notification)
    return notification
