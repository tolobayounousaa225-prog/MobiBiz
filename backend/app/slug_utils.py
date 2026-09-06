import random
import re
import string
import unicodedata

from sqlalchemy.orm import Session

from . import models

_REFERRAL_ALPHABET = string.ascii_uppercase + string.digits


def sanitize_slug(text: str) -> str:
    """Normalise un texte en segment d'URL valide (accents retirés, tout
    caractère non alphanumérique remplacé par un tiret) — SANS repli implicite
    sur une valeur par défaut : un texte qui ne contient rien d'utilisable (que
    des symboles, par ex.) renvoie une chaîne vide, à l'appelant de décider quoi
    en faire. Une personnalisation manuelle de lien doit être rejetée clairement
    dans ce cas, pas silencieusement remplacée par un mot générique."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()


def generate_unique_shop_slug(db: Session, nom: str) -> str:
    base = sanitize_slug(nom) or "boutique"
    slug = base
    suffix = 1
    while db.query(models.Shop).filter(models.Shop.slug == slug).first() is not None:
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


def generate_unique_referral_code(db: Session) -> str:
    while True:
        code = "".join(random.choices(_REFERRAL_ALPHABET, k=6))
        if db.query(models.Shop).filter(models.Shop.referral_code == code).first() is None:
            return code
