import csv
import io
from datetime import date as date_type

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop
from ..reports_pdf import generate_finance_report_pdf, generate_sales_report_pdf
from ..security_utils import csv_safe

router = APIRouter(prefix="/api/rapports", tags=["rapports"])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


def _csv_response(rows: list[list], header: list[str], filename: str) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ventes.csv")
def export_ventes_csv(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    orders = (
        db.query(models.Order)
        .options(joinedload(models.Order.customer), joinedload(models.Order.items).joinedload(models.OrderItem.product))
        .filter(models.Order.shop_id == shop.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    rows = []
    for order in orders:
        for item in order.items:
            rows.append([
                order.numero,
                order.created_at.date().isoformat(),
                csv_safe(order.customer.nom if order.customer else ""),
                csv_safe(item.product.nom if item.product else ""),
                item.quantite,
                item.prix_unitaire,
                order.statut.value,
                order.paiement_statut.value,
            ])
    header = ["Numéro commande", "Date", "Client", "Produit", "Quantité", "Prix unitaire", "Statut", "Paiement"]
    return _csv_response(rows, header, "ventes.csv")


@router.get("/produits.csv")
def export_produits_csv(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    products = db.query(models.Product).filter(models.Product.shop_id == shop.id).order_by(models.Product.nom).all()
    rows = [
        [
            csv_safe(p.reference or ""),
            csv_safe(p.nom),
            p.prix_achat,
            p.prix_vente,
            p.stock,
            p.seuil_alerte,
            "Oui" if p.stock <= p.seuil_alerte else "Non",
        ]
        for p in products
    ]
    header = ["Référence", "Nom", "Prix d'achat", "Prix de vente", "Stock", "Seuil d'alerte", "Stock faible"]
    return _csv_response(rows, header, "produits.csv")


@router.get("/clients.csv")
def export_clients_csv(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    customers = db.query(models.Customer).filter(models.Customer.shop_id == shop.id).order_by(models.Customer.nom).all()
    rows = [
        [
            csv_safe(c.nom),
            csv_safe(c.telephone or ""),
            csv_safe(c.email or ""),
            csv_safe(c.commune or ""),
        ]
        for c in customers
    ]
    header = ["Nom", "Téléphone", "Email", "Commune"]
    return _csv_response(rows, header, "clients.csv")


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ventes.pdf")
def export_ventes_pdf(
    date_debut: date_type | None = None,
    date_fin: date_type | None = None,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Order)
        .options(joinedload(models.Order.customer), joinedload(models.Order.items).joinedload(models.OrderItem.product))
        .filter(models.Order.shop_id == shop.id, ~models.Order.statut.in_(CANCELLED_STATUSES))
    )
    if date_debut:
        query = query.filter(models.Order.created_at >= date_debut)
    if date_fin:
        query = query.filter(models.Order.created_at < date_fin)
    orders = query.order_by(models.Order.created_at.desc()).all()

    pdf_bytes = generate_sales_report_pdf(shop, orders, date_debut, date_fin)
    return _pdf_response(pdf_bytes, "rapport-ventes.pdf")


@router.get("/finances.pdf")
def export_finances_pdf(
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
    expenses = expenses_query.all()
    depenses = sum(e.montant for e in expenses)

    summary = schemas.FinanceSummaryOut(
        chiffre_affaires=chiffre_affaires,
        cout_produits=cout_produits,
        depenses=depenses,
        benefice=chiffre_affaires - cout_produits - depenses,
    )
    pdf_bytes = generate_finance_report_pdf(shop, summary, expenses, date_debut, date_fin)
    return _pdf_response(pdf_bytes, "rapport-financier.pdf")
