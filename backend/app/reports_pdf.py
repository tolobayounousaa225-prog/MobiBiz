"""Rapports PDF (ventes, finances) — même choix technique que invoice.py :
reportlab, pur Python, pas de dépendance système supplémentaire sur Railway."""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from . import models, schemas
from .pdf_utils import shop_header_elements

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("ReportTitle", parent=_STYLES["Title"], fontSize=20, spaceAfter=2 * mm)
_SMALL = ParagraphStyle("ReportSmall", parent=_STYLES["Normal"], fontSize=9, textColor=colors.HexColor("#5b6072"))


def _fcfa(value: float) -> str:
    return f"{value:,.0f} FCFA".replace(",", " ")


def _period_label(date_debut: date | None, date_fin: date | None) -> str:
    if date_debut and date_fin:
        return f"Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"
    if date_debut:
        return f"Depuis le {date_debut.strftime('%d/%m/%Y')}"
    if date_fin:
        return f"Jusqu'au {date_fin.strftime('%d/%m/%Y')}"
    return "Toute la période"


def _base_doc(
    shop: "models.Shop", subtitle: str, date_debut: date | None, date_fin: date | None,
    logo_bytes: bytes | None = None,
) -> tuple[SimpleDocTemplate, io.BytesIO, list]:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = shop_header_elements(shop.nom, logo_bytes, _TITLE, [
        Paragraph(subtitle, _STYLES["Heading2"]),
        Paragraph(_period_label(date_debut, date_fin), _SMALL),
        Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", _SMALL),
    ])
    elements.append(Spacer(1, 8 * mm))
    return doc, buffer, elements


def _kpi_table(pairs: list[tuple[str, str]]) -> Table:
    table = Table([[label, value] for label, value in pairs], colWidths=[100 * mm, 70 * mm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7e9f0")),
    ]))
    return table


def _data_table(header: list[str], rows: list[list[str]], col_widths: list[float]) -> Table:
    table = Table([header, *rows], colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1d29")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7e9f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafd")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def generate_sales_report_pdf(
    shop: "models.Shop",
    orders: list["models.Order"],
    date_debut: date | None,
    date_fin: date | None,
    logo_bytes: bytes | None = None,
) -> bytes:
    doc, buffer, elements = _base_doc(shop, "Rapport de ventes", date_debut, date_fin, logo_bytes)

    chiffre_affaires = sum(o.total for o in orders)
    nombre_commandes = len(orders)
    panier_moyen = chiffre_affaires / nombre_commandes if nombre_commandes else 0

    elements.append(_kpi_table([
        ("Chiffre d'affaires", _fcfa(chiffre_affaires)),
        ("Nombre de commandes", str(nombre_commandes)),
        ("Panier moyen", _fcfa(panier_moyen)),
    ]))
    elements.append(Spacer(1, 8 * mm))

    ventes_par_produit: dict[str, tuple[int, float]] = {}
    for order in orders:
        for item in order.items:
            nom = item.product.nom if item.product else f"Produit #{item.product_id}"
            if item.variant_nom:
                nom += f" ({item.variant_nom})"
            qte, ca = ventes_par_produit.get(nom, (0, 0.0))
            ventes_par_produit[nom] = (qte + item.quantite, ca + item.prix_unitaire * item.quantite)

    top = sorted(ventes_par_produit.items(), key=lambda kv: kv[1][1], reverse=True)[:15]
    if top:
        elements.append(Paragraph("Produits les plus vendus", _STYLES["Heading3"]))
        elements.append(_data_table(
            ["Produit", "Qté vendue", "Chiffre d'affaires"],
            [[nom, str(qte), _fcfa(ca)] for nom, (qte, ca) in top],
            [90 * mm, 30 * mm, 50 * mm],
        ))
        elements.append(Spacer(1, 8 * mm))

    if orders:
        elements.append(Paragraph("Détail des commandes", _STYLES["Heading3"]))
        rows = [
            [o.numero, o.created_at.strftime("%d/%m/%Y"), o.customer_nom or "-", o.statut.value, _fcfa(o.total)]
            for o in orders[:200]
        ]
        elements.append(_data_table(
            ["N°", "Date", "Client", "Statut", "Total"],
            rows,
            [35 * mm, 25 * mm, 55 * mm, 30 * mm, 25 * mm],
        ))
        if len(orders) > 200:
            elements.append(Spacer(1, 3 * mm))
            elements.append(Paragraph(f"… et {len(orders) - 200} commande(s) supplémentaire(s) non affichée(s).", _SMALL))

    doc.build(elements)
    return buffer.getvalue()


def generate_finance_report_pdf(
    shop: "models.Shop",
    summary: "schemas.FinanceSummaryOut",
    expenses: list["models.Expense"],
    date_debut: date | None,
    date_fin: date | None,
    logo_bytes: bytes | None = None,
) -> bytes:
    doc, buffer, elements = _base_doc(shop, "Rapport financier", date_debut, date_fin, logo_bytes)

    elements.append(_kpi_table([
        ("Chiffre d'affaires", _fcfa(summary.chiffre_affaires)),
        ("Coût des produits vendus", _fcfa(summary.cout_produits)),
        ("Dépenses", _fcfa(summary.depenses)),
        ("Bénéfice net", _fcfa(summary.benefice)),
    ]))
    elements.append(Spacer(1, 8 * mm))

    if expenses:
        par_categorie: dict[str, float] = {}
        for e in expenses:
            par_categorie[e.categorie.value] = par_categorie.get(e.categorie.value, 0) + e.montant

        elements.append(Paragraph("Dépenses par catégorie", _STYLES["Heading3"]))
        elements.append(_data_table(
            ["Catégorie", "Montant"],
            [[cat.capitalize(), _fcfa(montant)] for cat, montant in sorted(par_categorie.items(), key=lambda kv: kv[1], reverse=True)],
            [110 * mm, 60 * mm],
        ))
        elements.append(Spacer(1, 8 * mm))

        elements.append(Paragraph("Détail des dépenses", _STYLES["Heading3"]))
        rows = [
            [e.date.strftime("%d/%m/%Y"), e.categorie.value.capitalize(), e.libelle, _fcfa(e.montant)]
            for e in sorted(expenses, key=lambda e: e.date, reverse=True)[:200]
        ]
        elements.append(_data_table(
            ["Date", "Catégorie", "Libellé", "Montant"],
            rows,
            [25 * mm, 30 * mm, 85 * mm, 30 * mm],
        ))

    doc.build(elements)
    return buffer.getvalue()
