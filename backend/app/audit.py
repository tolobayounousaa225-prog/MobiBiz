from sqlalchemy.orm import Session

from . import models


def log_admin_action(
    db: Session,
    admin: models.User,
    action: str,
    cible_type: str,
    cible_id: int | None = None,
    details: str | None = None,
) -> None:
    """N'appelle jamais commit() — laisse l'appelant décider du point de commit,
    généralement dans la même transaction que l'action tracée."""
    db.add(models.AuditLog(
        admin_id=admin.id, action=action, cible_type=cible_type, cible_id=cible_id, details=details,
    ))
