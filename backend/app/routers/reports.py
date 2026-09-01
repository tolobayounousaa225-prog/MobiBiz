import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..deps import get_current_shop
from ..security_utils import csv_safe

router = APIRouter(prefix="/api/rapports", tags=["rapports"])


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
