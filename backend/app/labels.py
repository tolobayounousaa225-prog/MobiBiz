"""Étiquettes produit imprimables (QR code + nom + prix) — aide à la vente et à
l'inventaire en boutique physique. QR plutôt qu'un vrai code-barres EAN13 (qui
nécessite un identifiant normalisé attribué par GS1, hors de portée ici) :
encode simplement une référence lisible par n'importe quel scanner QR, y compris
un smartphone, sans matériel dédié."""

import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from . import models

_STYLES = getSampleStyleSheet()
_LABEL_NOM = ParagraphStyle("LabelNom", parent=_STYLES["Normal"], fontSize=8.5, fontName="Helvetica-Bold", leading=10)
_LABEL_INFO = ParagraphStyle("LabelInfo", parent=_STYLES["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#5b6072"))

_COLS = 3
_LABEL_W = 58 * mm
_LABEL_H = 30 * mm
_QR_SIZE = 22 * mm

_MAX_LABELS = 60


def _qr_png_bytes(data: str) -> bytes:
    img = qrcode.make(data, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_product_labels_pdf(product: "models.Product", shop: "models.Shop", quantite: int = 12) -> bytes:
    quantite = max(1, min(quantite, _MAX_LABELS))

    qr_data = f"MOBIBIZ|{shop.slug}|{product.reference or product.id}"
    qr_png = _qr_png_bytes(qr_data)

    prix = f"{product.effective_price:,.0f} FCFA".replace(",", " ")

    def make_label() -> Table:
        # Chaque étiquette doit être une instance de flowable neuve — reportlab ne
        # supporte pas de réutiliser le même objet Table/Image/Paragraph à
        # plusieurs endroits d'un même document (état de mise en page partagé,
        # rendu incorrect silencieux sinon).
        texte = [Paragraph(product.nom, _LABEL_NOM)]
        if product.reference:
            texte.append(Paragraph(f"Réf. {product.reference}", _LABEL_INFO))
        texte.append(Paragraph(prix, _LABEL_INFO))

        label = Table(
            [[RLImage(io.BytesIO(qr_png), width=_QR_SIZE, height=_QR_SIZE), texte]],
            colWidths=[_QR_SIZE + 2 * mm, _LABEL_W - _QR_SIZE - 2 * mm],
            rowHeights=[_LABEL_H - 4 * mm],
        )
        label.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7c9d8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        return label

    rows = []
    row = []
    for i in range(quantite):
        row.append(make_label())
        if len(row) == _COLS:
            rows.append(row)
            row = []
    if row:
        while len(row) < _COLS:
            row.append("")
        rows.append(row)

    grid = Table(rows, colWidths=[_LABEL_W] * _COLS, rowHeights=[_LABEL_H] * len(rows))
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10 * mm, bottomMargin=10 * mm, leftMargin=10 * mm, rightMargin=10 * mm)
    doc.build([grid])
    return buffer.getvalue()
