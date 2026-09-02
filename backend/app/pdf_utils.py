"""Utilitaires PDF partagés — en-tête avec logo boutique et bloc de certification
QR, réutilisés par les factures, les rapports et les reçus de paiement pour ne
pas dupliquer la mise en page à chaque endroit."""

import io

import qrcode
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

LOGO_MAX_SIZE = 22 * mm
_QR_SIZE = 24 * mm
_QR_LABEL_STYLE = ParagraphStyle(
    "QrLabel", parent=getSampleStyleSheet()["Normal"], fontSize=8.5,
    textColor=colors.HexColor("#5b6072"), leading=11,
)


def _fit_size(image_bytes: bytes, max_size: float) -> tuple[float, float]:
    with PILImage.open(io.BytesIO(image_bytes)) as im:
        width, height = im.size
    scale = min(max_size / width, max_size / height)
    return width * scale, height * scale


def shop_header_elements(
    shop_nom: str,
    logo_bytes: bytes | None,
    title_style: ParagraphStyle,
    subtitle_elements: list,
) -> list:
    """Retourne les flowables d'en-tête : nom de la boutique (+ sous-titres) seul,
    ou accompagné du logo à gauche si la boutique en a uploadé un. Un logo
    illisible/corrompu ne doit jamais faire échouer la génération du document —
    on retombe simplement sur l'en-tête textuel seul."""
    text_block = [Paragraph(shop_nom, title_style), *subtitle_elements]
    if not logo_bytes:
        return text_block

    try:
        width, height = _fit_size(logo_bytes, LOGO_MAX_SIZE)
        logo_image = RLImage(io.BytesIO(logo_bytes), width=width, height=height)
    except Exception:
        return text_block

    table = Table([[logo_image, text_block]], colWidths=[LOGO_MAX_SIZE + 5 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [table]


def verification_qr_elements(verify_url: str, caption: str) -> list:
    """QR code de certification — scanné, il ouvre une page publique qui confirme
    que ce document correspond bien à un enregistrement réel sur la plateforme
    (commande ou paiement d'abonnement), avec les mêmes infos clés affichées ici.
    Un QR illisible ne doit jamais faire échouer la génération du document."""
    try:
        qr_img = qrcode.make(verify_url, border=2)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        qr_png = buf.getvalue()
        qr_flowable = RLImage(io.BytesIO(qr_png), width=_QR_SIZE, height=_QR_SIZE)
    except Exception:
        return []

    table = Table(
        [[qr_flowable, Paragraph(caption, _QR_LABEL_STYLE)]],
        colWidths=[_QR_SIZE + 4 * mm, 70 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [table]
