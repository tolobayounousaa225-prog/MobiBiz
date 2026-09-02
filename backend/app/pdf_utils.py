"""Utilitaires PDF partagés — en-tête avec logo boutique, réutilisé par les
factures et les rapports pour ne pas dupliquer la mise en page trois fois."""

import io

from PIL import Image as PILImage
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

LOGO_MAX_SIZE = 22 * mm


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
