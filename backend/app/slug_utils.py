import re
import unicodedata

from sqlalchemy.orm import Session

from . import models


def _base_slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "boutique"


def generate_unique_shop_slug(db: Session, nom: str) -> str:
    base = _base_slug(nom)
    slug = base
    suffix = 1
    while db.query(models.Shop).filter(models.Shop.slug == slug).first() is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug
