from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..rate_limit import enforce_login_rate_limit
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce numéro est déjà utilisé")

    if payload.email:
        existing_email = db.query(models.User).filter(models.User.email == payload.email).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet email est déjà utilisé")

    user = models.User(
        nom=payload.nom,
        prenom=payload.prenom,
        telephone=payload.telephone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=models.UserRole.OWNER,
    )
    db.add(user)
    db.flush()

    shop = models.Shop(owner_id=user.id, nom=payload.boutique_nom)
    db.add(shop)
    db.commit()

    token = create_access_token(str(user.id))
    return schemas.TokenOut(access_token=token)


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    enforce_login_rate_limit(request)

    user = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Numéro ou mot de passe incorrect")
    if user is None or not verify_password(payload.password, user.password_hash):
        raise invalid
    if not user.actif:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    token = create_access_token(str(user.id))
    return schemas.TokenOut(access_token=token)


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
