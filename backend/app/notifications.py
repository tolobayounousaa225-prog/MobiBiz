from sqlalchemy.orm import Session

from . import models


def notify(
    db: Session,
    shop_id: int,
    type_: models.NotificationType,
    message: str,
    order_id: int | None = None,
) -> None:
    """Ajoute une notification in-app à la boutique. N'appelle jamais commit() —
    laisse l'appelant décider du point de commit (généralement dans la même
    transaction que l'action qui déclenche la notification)."""
    db.add(models.Notification(shop_id=shop_id, type=type_, message=message, order_id=order_id))
