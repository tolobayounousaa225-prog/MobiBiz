from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..plans import TRIAL_DAYS
from ..rate_limit import enforce_login_rate_limit, enforce_password_reset_rate_limit
from ..security import (
    create_access_token,
    hash_password,
    hash_security_answer,
    verify_password,
    verify_security_answer,
)
from ..slug_utils import generate_unique_shop_slug

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

    if payload.security_question not in schemas.SECURITY_QUESTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question de sécurité invalide")

    user = models.User(
        nom=payload.nom,
        prenom=payload.prenom,
        telephone=payload.telephone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=models.UserRole.OWNER,
        security_question=payload.security_question,
        security_answer_hash=hash_security_answer(payload.security_answer),
    )
    db.add(user)
    db.flush()

    slug = generate_unique_shop_slug(db, payload.boutique_nom)
    shop = models.Shop(
        owner_id=user.id, nom=payload.boutique_nom, slug=slug,
        essai_expire_le=date.today() + timedelta(days=TRIAL_DAYS),
    )
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


@router.get("/questions-securite")
def list_security_questions():
    return {"questions": schemas.SECURITY_QUESTIONS}


@router.put("/question-securite", response_model=schemas.UserOut)
def update_security_question(
    payload: schemas.SecurityQuestionUpdateIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.security_question not in schemas.SECURITY_QUESTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question de sécurité invalide")
    current_user.security_question = payload.security_question
    current_user.security_answer_hash = hash_security_answer(payload.security_answer)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: schemas.PasswordChangeIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.ancien_mot_de_passe, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mot de passe actuel incorrect")
    current_user.password_hash = hash_password(payload.nouveau_mot_de_passe)
    db.commit()


@router.post("/mot-de-passe-oublie/question", response_model=schemas.ForgotPasswordQuestionOut)
def forgot_password_question(payload: schemas.ForgotPasswordQuestionIn, request: Request, db: Session = Depends(get_db)):
    enforce_password_reset_rate_limit(request, payload.telephone)
    user = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    if user is None or not user.has_security_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune question de sécurité disponible pour ce numéro. Contactez le propriétaire de la boutique.",
        )
    return schemas.ForgotPasswordQuestionOut(question=user.security_question)


@router.post("/mot-de-passe-oublie/reinitialiser", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password_reset(payload: schemas.ForgotPasswordResetIn, request: Request, db: Session = Depends(get_db)):
    enforce_password_reset_rate_limit(request, payload.telephone)
    user = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Réponse incorrecte")
    if user is None or not user.has_security_question:
        raise invalid
    if not verify_security_answer(payload.reponse, user.security_answer_hash):
        raise invalid
    user.password_hash = hash_password(payload.nouveau_mot_de_passe)
    db.commit()
