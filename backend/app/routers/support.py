from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, get_current_user

router = APIRouter(prefix="/api/support", tags=["support"])


def _ticket_to_out(ticket: models.SupportTicket) -> schemas.TicketOut:
    return schemas.TicketOut(
        id=ticket.id, sujet=ticket.sujet, statut=ticket.statut,
        boutique_nom=ticket.shop.nom if ticket.shop else None, created_at=ticket.created_at,
        messages=[
            schemas.TicketMessageOut(
                id=m.id, auteur_id=m.auteur_id, auteur_nom=f"{m.auteur.prenom} {m.auteur.nom}",
                auteur_role=m.auteur.role, message=m.message, created_at=m.created_at,
            )
            for m in ticket.messages
        ],
    )


def _get_owned_ticket(db: Session, shop: models.Shop, ticket_id: int) -> models.SupportTicket:
    ticket = (
        db.query(models.SupportTicket)
        .filter(models.SupportTicket.id == ticket_id, models.SupportTicket.shop_id == shop.id)
        .first()
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket introuvable")
    return ticket


@router.get("/tickets", response_model=list[schemas.TicketOut])
def list_my_tickets(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    tickets = (
        db.query(models.SupportTicket)
        .filter(models.SupportTicket.shop_id == shop.id)
        .order_by(models.SupportTicket.created_at.desc())
        .all()
    )
    return [_ticket_to_out(t) for t in tickets]


@router.post("/tickets", response_model=schemas.TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: schemas.TicketCreateIn,
    shop: models.Shop = Depends(get_current_shop),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = models.SupportTicket(shop_id=shop.id, sujet=payload.sujet)
    db.add(ticket)
    db.flush()
    db.add(models.TicketMessage(ticket_id=ticket.id, auteur_id=current_user.id, message=payload.message))
    db.commit()
    db.refresh(ticket)
    return _ticket_to_out(ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=schemas.TicketOut, status_code=status.HTTP_201_CREATED)
def reply_ticket(
    ticket_id: int,
    payload: schemas.TicketMessageIn,
    shop: models.Shop = Depends(get_current_shop),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = _get_owned_ticket(db, shop, ticket_id)
    db.add(models.TicketMessage(ticket_id=ticket.id, auteur_id=current_user.id, message=payload.message))
    db.commit()
    db.refresh(ticket)
    return _ticket_to_out(ticket)
