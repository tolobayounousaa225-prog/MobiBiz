"""Suivi de commande public — le client garde le numéro de commande donné à la
validation et peut consulter le statut/livraison à tout moment sans compte,
en le partageant lui-même (aucun SMS/email automatique)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..rate_limit import enforce_verification_rate_limit

router = APIRouter(prefix="/api/public/suivi", tags=["suivi"])


@router.get("/{numero}", response_model=schemas.OrderTrackingOut)
def track_order(numero: str, request: Request, db: Session = Depends(get_db)):
    enforce_verification_rate_limit(request)
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.product))
        .filter(models.Order.numero == numero)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commande introuvable")

    return schemas.OrderTrackingOut(
        numero=order.numero,
        boutique_nom=order.shop.nom,
        statut=order.statut,
        paiement_statut=order.paiement_statut,
        total=order.total,
        mode_livraison=order.mode_livraison,
        livreur_nom=order.livreur_nom,
        adresse_livraison=order.adresse_livraison,
        commune_livraison=order.commune_livraison,
        heure_livraison_prevue=order.heure_livraison_prevue,
        created_at=order.created_at,
        items=[
            schemas.OrderTrackingItemOut(
                nom=item.product.nom if item.product else f"Produit #{item.product_id}",
                variante=item.variant_nom,
                quantite=item.quantite,
            )
            for item in order.items
        ],
    )
