"""Génération de facture PDF pour une commande. reportlab est pur Python (pas de
dépendance système comme pango/cairo pour weasyprint), donc s'installe sans souci
sur l'image Docker Railway — critère qui avait déjà guidé le choix de qrcode/Pillow
pour les QR codes Wave."""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from . import models
from .pdf_utils import shop_header_elements


def generate_invoice_pdf(order: "models.Order", shop: "models.Shop", logo_bytes: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontSize=20, spaceAfter=2 * mm)
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#5b6072"))

    elements = shop_header_elements(
        shop.nom, logo_bytes, title_style,
        [Paragraph(" · ".join(filter(None, [shop.adresse, shop.commune, shop.telephone])) or "", small)],
    )
    elements += [
        Spacer(1, 8 * mm),
        Paragraph(f"Facture — Commande {order.numero}", styles["Heading2"]),
        Paragraph(f"Date : {order.created_at.strftime('%d/%m/%Y')}", normal),
        Paragraph(f"Client : {order.customer_nom or '-'} ({order.customer_telephone or '-'})", normal),
        Spacer(1, 6 * mm),
    ]

    rows = [["Produit", "Qté", "Prix unitaire", "Sous-total"]]
    for item in order.items:
        libelle = item.product.nom if item.product else f"Produit #{item.product_id}"
        if item.variant_nom:
            libelle += f" ({item.variant_nom})"
        rows.append([
            libelle,
            str(item.quantite),
            f"{item.prix_unitaire:,.0f} FCFA".replace(",", " "),
            f"{item.prix_unitaire * item.quantite:,.0f} FCFA".replace(",", " "),
        ])

    table = Table(rows, colWidths=[80 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1d29")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7e9f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafd")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    sous_total = sum(item.prix_unitaire * item.quantite for item in order.items)
    totals_rows = [["Sous-total", f"{sous_total:,.0f} FCFA".replace(",", " ")]]
    if order.reduction:
        label = f"Réduction (code {order.coupon_code})" if order.coupon_code else "Réduction"
        totals_rows.append([label, f"- {order.reduction:,.0f} FCFA".replace(",", " ")])
    if order.frais_livraison:
        totals_rows.append(["Frais de livraison", f"{order.frais_livraison:,.0f} FCFA".replace(",", " ")])
    totals_rows.append(["Total", f"{order.total:,.0f} FCFA".replace(",", " ")])

    totals_table = Table(totals_rows, colWidths=[135 * mm, 35 * mm])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#1a1d29")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(f"Statut du paiement : {order.paiement_statut.value}", small))
    elements.append(Paragraph("Généré par MobiBiz", small))

    doc.build(elements)
    return buffer.getvalue()
