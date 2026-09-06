"""Visuel de partage produit (réseaux sociaux) — image carrée générée avec
Pillow (déjà une dépendance), pas d'IA. La police par défaut de Pillow
(ImageFont.load_default) ne couvre pas les accents/tirets typographiques
français — translittérer le texte avant de le dessiner sur cette image
uniquement, jamais le contenu réel du site (même piège déjà rencontré sur
LECIM avec les visuels de partage d'actualités)."""

import io
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from . import models

SIZE = 1080
PHOTO_HEIGHT = int(SIZE * 0.62)


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _cover_fit(img: Image.Image, width: int, height: int) -> Image.Image:
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_height = height
        new_width = int(height * src_ratio)
    else:
        new_width = width
        new_height = int(width / src_ratio)
    img = img.resize((new_width, new_height))
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def generate_product_share_image(product: "models.Product", shop: "models.Shop", photo_bytes: bytes | None) -> bytes:
    img = Image.new("RGB", (SIZE, SIZE), color=(26, 29, 41))

    if photo_bytes:
        try:
            photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            photo = _cover_fit(photo, SIZE, PHOTO_HEIGHT)
            img.paste(photo, (0, 0))
        except Exception:
            pass

    draw = ImageDraw.Draw(img)
    font_name = ImageFont.load_default(size=58)
    font_price = ImageFont.load_default(size=64)
    font_shop = ImageFont.load_default(size=30)
    font_badge = ImageFont.load_default(size=30)

    y = PHOTO_HEIGHT + 50
    draw.text((50, y), _ascii(product.nom), font=font_name, fill=(255, 255, 255))

    y += 80
    prix = f"{product.effective_price:,.0f} FCFA".replace(",", " ")
    if product.promo_actif and product.prix_promo is not None:
        ancien = f"{product.prix_vente:,.0f} FCFA".replace(",", " ")
        draw.text((50, y), _ascii(ancien), font=font_badge, fill=(150, 152, 168))
        # Barre le prix barré à la main (pas de style texte dans Pillow par défaut)
        bbox = draw.textbbox((50, y), _ascii(ancien), font=font_badge)
        draw.line((bbox[0], (bbox[1] + bbox[3]) // 2, bbox[2], (bbox[1] + bbox[3]) // 2), fill=(150, 152, 168), width=2)
        y += 40
    draw.text((50, y), _ascii(prix), font=font_price, fill=(255, 122, 0))

    draw.text((50, SIZE - 60), _ascii(shop.nom), font=font_shop, fill=(199, 201, 216))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
