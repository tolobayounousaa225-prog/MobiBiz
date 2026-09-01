from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(models.User, int(user_id))
    if user is None or not user.actif:
        raise unauthorized
    return user


def get_current_shop(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Shop:
    if current_user.role == models.UserRole.EMPLOYEE:
        shop = db.get(models.Shop, current_user.shop_id) if current_user.shop_id else None
    else:
        shop = db.query(models.Shop).filter(models.Shop.owner_id == current_user.id).first()
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune boutique associée à ce compte")
    return shop


def require_module(module: str):
    """Fabrique de dépendance : autorise le propriétaire (toujours) et les employés
    dont le rôle donne accès à ce module (voir models.EMPLOYEE_MODULE_ACCESS,
    section 24 du cahier des charges). Utiliser comme
    Depends(require_module("finance")) sur les routes à restreindre."""

    def checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not current_user.has_module_access(module):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne donne pas accès à cette fonctionnalité",
            )
        return current_user

    return checker


def require_any_module(*modules: str):
    """Comme require_module, mais autorise l'accès si le rôle donne accès à
    N'IMPORTE LEQUEL des modules listés — utile pour une lecture partagée entre
    plusieurs métiers (ex: le catalogue produit, consulté aussi bien pour le gérer
    que pour composer une commande)."""

    def checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not any(current_user.has_module_access(m) for m in modules):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne donne pas accès à cette fonctionnalité",
            )
        return current_user

    return checker


def require_owner(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé au propriétaire de la boutique",
        )
    return current_user
