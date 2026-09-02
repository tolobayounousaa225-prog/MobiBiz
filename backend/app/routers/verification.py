"""Vérification publique de reçus/factures via QR — aucune authentification
(un client scannant un reçu papier ou un PDF n'a pas de compte). Volontairement
minimal dans ce qui est exposé : assez pour confirmer l'authenticité (boutique,
montant, date, statut) sans révéler les coordonnées du client final."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rate_limit import enforce_verification_rate_limit

router = APIRouter(prefix="/api/public/verification", tags=["verification"])


@router.get("/commande/{numero}", response_model=schemas.OrderVerificationOut)
def verify_order(numero: str, request: Request, db: Session = Depends(get_db)):
    enforce_verification_rate_limit(request)
    order = db.query(models.Order).filter(models.Order.numero == numero).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucune commande ne correspond à ce reçu")
    return schemas.OrderVerificationOut(
        numero=order.numero,
        boutique_nom=order.shop.nom,
        date=order.created_at,
        total=order.total,
        statut=order.statut,
        paiement_statut=order.paiement_statut,
    )


@router.get("/paiement/{reference}", response_model=schemas.PaymentVerificationOut)
def verify_payment(reference: str, request: Request, db: Session = Depends(get_db)):
    enforce_verification_rate_limit(request)
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun paiement ne correspond à ce reçu")
    if not reference.upper().startswith("PAY-"):
        raise not_found
    try:
        payment_id = int(reference.upper().removeprefix("PAY-"))
    except ValueError:
        raise not_found

    payment = db.get(models.SubscriptionPayment, payment_id)
    if payment is None:
        raise not_found
    return schemas.PaymentVerificationOut(
        reference=reference.upper(),
        boutique_nom=payment.shop.nom,
        montant=payment.montant,
        date_paiement=payment.date_paiement,
    )
