import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_module
from ..notifications import notify

router = APIRouter(prefix="/api/commandes", tags=["commandes"], dependencies=[Depends(require_module("commandes"))])

# Transitions autorisées pour la machine à états des commandes (section 13 du cahier des charges)
ALLOWED_TRANSITIONS: dict[models.OrderStatus, set[models.OrderStatus]] = {
    models.OrderStatus.NOUVELLE: {models.OrderStatus.CONFIRMEE, models.OrderStatus.ANNULEE},
    models.OrderStatus.CONFIRMEE: {models.OrderStatus.EN_PREPARATION, models.OrderStatus.ANNULEE},
    models.OrderStatus.EN_PREPARATION: {models.OrderStatus.EXPEDIEE, models.OrderStatus.ANNULEE},
    models.OrderStatus.EXPEDIEE: {models.OrderStatus.LIVREE, models.OrderStatus.ECHOUEE},
    models.OrderStatus.LIVREE: {models.OrderStatus.TERMINEE, models.OrderStatus.RETOURNEE},
    models.OrderStatus.TERMINEE: set(),
    models.OrderStatus.ANNULEE: set(),
    models.OrderStatus.RETOURNEE: set(),
    models.OrderStatus.ECHOUEE: set(),
}

RESTOCKING_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.RETOURNEE, models.OrderStatus.ECHOUEE}


def _generate_order_number(db: Session, shop_id: int) -> str:
    while True:
        suffix = "".join(secrets.choice(string.digits) for _ in range(6))
        numero = f"CMD-{shop_id}-{suffix}"
        if not db.query(models.Order).filter(models.Order.numero == numero).first():
            return numero


def _get_owned_order(db: Session, shop: models.Shop, order_id: int) -> models.Order:
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items), joinedload(models.Order.customer))
        .filter(models.Order.id == order_id, models.Order.shop_id == shop.id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commande introuvable")
    return order


@router.get("", response_model=list[schemas.OrderOut])
def list_orders(
    statut: models.OrderStatus | None = None,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Order)
        .options(joinedload(models.Order.items), joinedload(models.Order.customer))
        .filter(models.Order.shop_id == shop.id)
    )
    if statut:
        query = query.filter(models.Order.statut == statut)
    return query.order_by(models.Order.created_at.desc()).all()


@router.post("", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: schemas.OrderIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La commande doit contenir au moins un produit")

    if payload.customer_id is not None:
        customer = (
            db.query(models.Customer)
            .filter(models.Customer.id == payload.customer_id, models.Customer.shop_id == shop.id)
            .first()
        )
        if customer is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client invalide")
    elif payload.nouveau_client is not None:
        customer = models.Customer(shop_id=shop.id, **payload.nouveau_client.model_dump())
        db.add(customer)
        db.flush()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client requis (existant ou nouveau)")

    order = models.Order(
        shop_id=shop.id,
        customer_id=customer.id,
        numero=_generate_order_number(db, shop.id),
        reduction=payload.reduction,
        frais_livraison=payload.frais_livraison,
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    sous_total = 0.0
    for item in payload.items:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id, models.Product.shop_id == shop.id)
            .first()
        )
        if product is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Produit {item.product_id} invalide")
        if product.stock < item.quantite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuffisant pour « {product.nom} » (disponible : {product.stock})",
            )

        stock_avant = product.stock
        product.stock -= item.quantite
        db.add(models.StockMovement(product_id=product.id, type=models.StockMovementType.VENTE, quantite=-item.quantite))

        if product.stock <= product.seuil_alerte < stock_avant:
            notify(
                db, shop.id, models.NotificationType.STOCK_FAIBLE,
                f"Stock faible : « {product.nom} » (reste {product.stock})",
            )

        order_item = models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantite=item.quantite,
            prix_unitaire=product.effective_price,
            prix_achat_unitaire=product.prix_achat,
        )
        db.add(order_item)
        sous_total += product.effective_price * item.quantite

    order.total = max(sous_total - payload.reduction, 0) + payload.frais_livraison
    notify(
        db, shop.id, models.NotificationType.NOUVELLE_COMMANDE,
        f"Nouvelle commande {order.numero} de {customer.nom} — {order.total:.0f} FCFA",
        order_id=order.id,
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return _get_owned_order(db, shop, order_id)


@router.patch("/{order_id}/statut", response_model=schemas.OrderOut)
def update_order_status(
    order_id: int,
    payload: schemas.OrderStatusIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    order = _get_owned_order(db, shop, order_id)
    allowed = ALLOWED_TRANSITIONS.get(order.statut, set())
    if payload.statut != order.statut and payload.statut not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transition de « {order.statut.value} » vers « {payload.statut.value} » non autorisée",
        )

    if payload.statut in RESTOCKING_STATUSES and order.statut not in RESTOCKING_STATUSES:
        for item in order.items:
            product = db.get(models.Product, item.product_id)
            if product is not None:
                product.stock += item.quantite
                db.add(models.StockMovement(
                    product_id=product.id,
                    type=models.StockMovementType.ANNULATION,
                    quantite=item.quantite,
                    motif=f"Commande {order.numero} : {payload.statut.value}",
                ))

    order.statut = payload.statut
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/paiement", response_model=schemas.OrderOut)
def update_order_payment(
    order_id: int,
    payload: schemas.PaiementStatutIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    order = _get_owned_order(db, shop, order_id)
    if payload.paiement_statut == models.PaiementStatut.PAYE and order.paiement_statut != models.PaiementStatut.PAYE:
        notify(
            db, shop.id, models.NotificationType.PAIEMENT_RECU,
            f"Paiement reçu pour {order.numero} — {order.total:.0f} FCFA",
            order_id=order.id,
        )
    order.paiement_statut = payload.paiement_statut
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/livraison", response_model=schemas.OrderOut)
def update_order_delivery(
    order_id: int,
    payload: schemas.DeliveryUpdateIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    order = _get_owned_order(db, shop, order_id)
    for field, value in payload.model_dump().items():
        setattr(order, field, value)
    db.commit()
    db.refresh(order)
    return order
