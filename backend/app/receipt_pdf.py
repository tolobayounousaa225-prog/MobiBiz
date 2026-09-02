"""Reçu de paiement d'abonnement plateforme — émis par MobiBiz (pas par la
boutique elle-même, qui est ici le payeur), généré et rangé dans l'espace de la
boutique dès que l'admin confirme un paiement reçu. Traçabilité : l'admin peut
oublier de prévenir ou se tromper de montant en le disant de vive voix, le reçu
consultable à tout moment dans l'espace boutique ne dépend pas de ça."""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import models

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("ReceiptTitle", parent=_STYLES["Title"], fontSize=20, spaceAfter=2 * mm)
_SMALL = ParagraphStyle("ReceiptSmall", parent=_STYLES["Normal"], fontSize=9, textColor=colors.HexColor("#5b6072"))


def generate_payment_receipt_pdf(shop: "models.Shop", payment: "models.SubscriptionPayment") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=25 * mm, bottomMargin=25 * mm)

    rows = [
        ["Boutique", shop.nom],
        ["Montant réglé", f"{payment.montant:,.0f} FCFA".replace(",", " ")],
        ["Date de paiement", payment.date_paiement.strftime("%d/%m/%Y")],
        ["Enregistré le", payment.created_at.strftime("%d/%m/%Y à %H:%M")],
        ["Référence", f"PAY-{payment.id:06d}"],
    ]
    table = Table(rows, colWidths=[55 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e7e9f0")),
    ]))

    elements = [
        Paragraph("MobiBiz", _TITLE),
        Paragraph("Reçu de paiement d'abonnement", _STYLES["Heading2"]),
        Spacer(1, 8 * mm),
        table,
        Spacer(1, 10 * mm),
        Paragraph(
            "Ce reçu confirme la réception, par l'administrateur de la plateforme "
            "MobiBiz, du paiement de l'abonnement de votre boutique.",
            _SMALL,
        ),
    ]

    doc.build(elements)
    return buffer.getvalue()
