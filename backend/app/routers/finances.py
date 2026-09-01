from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_module

router = APIRouter(tags=["finances"], dependencies=[Depends(require_module("finance"))])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


def _get_owned_expense(db: Session, shop: models.Shop, expense_id: int) -> models.Expense:
    expense = (
        db.query(models.Expense)
        .filter(models.Expense.id == expense_id, models.Expense.shop_id == shop.id)
        .first()
    )
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dépense introuvable")
    return expense


@router.get("/api/depenses", response_model=list[schemas.ExpenseOut])
def list_expenses(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return (
        db.query(models.Expense)
        .filter(models.Expense.shop_id == shop.id)
        .order_by(models.Expense.date.desc())
        .all()
    )


@router.post("/api/depenses", response_model=schemas.ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: schemas.ExpenseIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    try:
        parsed_date = date_type.fromisoformat(payload.date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format attendu AAAA-MM-JJ)")

    expense = models.Expense(
        shop_id=shop.id,
        categorie=payload.categorie,
        libelle=payload.libelle,
        montant=payload.montant,
        date=parsed_date,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/api/depenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    expense = _get_owned_expense(db, shop, expense_id)
    db.delete(expense)
    db.commit()


@router.get("/api/finances/resume", response_model=schemas.FinanceSummaryOut)
def finance_summary(
    date_debut: date_type | None = None,
    date_fin: date_type | None = None,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    orders_query = db.query(models.Order).filter(
        models.Order.shop_id == shop.id, ~models.Order.statut.in_(CANCELLED_STATUSES)
    )
    if date_debut:
        orders_query = orders_query.filter(models.Order.created_at >= date_debut)
    if date_fin:
        orders_query = orders_query.filter(models.Order.created_at < date_fin)
    orders = orders_query.all()

    chiffre_affaires = sum(o.total for o in orders)
    cout_produits = sum(item.prix_achat_unitaire * item.quantite for o in orders for item in o.items)

    expenses_query = db.query(models.Expense).filter(models.Expense.shop_id == shop.id)
    if date_debut:
        expenses_query = expenses_query.filter(models.Expense.date >= date_debut)
    if date_fin:
        expenses_query = expenses_query.filter(models.Expense.date < date_fin)
    depenses = sum(e.montant for e in expenses_query.all())

    benefice = chiffre_affaires - cout_produits - depenses

    return schemas.FinanceSummaryOut(
        chiffre_affaires=chiffre_affaires,
        cout_produits=cout_produits,
        depenses=depenses,
        benefice=benefice,
    )
