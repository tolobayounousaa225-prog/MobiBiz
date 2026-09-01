from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop

router = APIRouter(prefix="/api/clients", tags=["clients"])

VIP_THRESHOLD = 200_000
INACTIVE_DAYS = 60


def _get_owned_customer(db: Session, shop: models.Shop, customer_id: int) -> models.Customer:
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == customer_id, models.Customer.shop_id == shop.id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable")
    return customer


def _to_stats(db: Session, customer: models.Customer) -> schemas.CustomerStats:
    orders = (
        db.query(models.Order)
        .filter(models.Order.customer_id == customer.id, models.Order.statut != models.OrderStatus.ANNULEE)
        .all()
    )
    total_achats = sum(o.total for o in orders)
    nombre_commandes = len(orders)
    derniere_commande = max((o.created_at for o in orders), default=None)

    if nombre_commandes == 0:
        segment = "nouveau"
    elif derniere_commande and models.ensure_aware(derniere_commande) < datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS):
        segment = "inactif"
    elif total_achats >= VIP_THRESHOLD:
        segment = "vip"
    elif nombre_commandes >= 3:
        segment = "regulier"
    else:
        segment = "nouveau"

    return schemas.CustomerStats(
        **schemas.CustomerOut.model_validate(customer).model_dump(),
        total_achats=total_achats,
        nombre_commandes=nombre_commandes,
        derniere_commande=derniere_commande,
        segment=segment,
    )


@router.get("", response_model=list[schemas.CustomerStats])
def list_customers(q: str | None = None, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    query = db.query(models.Customer).filter(models.Customer.shop_id == shop.id)
    if q:
        query = query.filter(models.Customer.nom.ilike(f"%{q}%"))
    customers = query.order_by(models.Customer.nom).all()
    return [_to_stats(db, c) for c in customers]


@router.post("", response_model=schemas.CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: schemas.CustomerIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    customer = models.Customer(shop_id=shop.id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=schemas.CustomerStats)
def get_customer(customer_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    customer = _get_owned_customer(db, shop, customer_id)
    return _to_stats(db, customer)


@router.put("/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(
    customer_id: int,
    payload: schemas.CustomerIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    customer = _get_owned_customer(db, shop, customer_id)
    for field, value in payload.model_dump().items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    customer = _get_owned_customer(db, shop, customer_id)
    db.delete(customer)
    db.commit()
