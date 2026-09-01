"""Stockage des fichiers uploadés (photos produit...) en base de données plutôt
que sur le disque du conteneur — voir `StoredFile` dans models.py pour le
contexte (Railway ne fournit pas de disque persistant)."""

import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from . import models
from .config import settings

ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024

# Signatures binaires (magic bytes) attendues pour chaque extension autorisée —
# défense en profondeur en plus du contrôle d'extension : empêche de stocker un
# contenu arbitraire simplement renommé avec une extension permise.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),  # "WEBP" suit à l'offset 8, vérifié séparément ci-dessous
}


def _matches_magic_bytes(data: bytes, ext: str) -> bool:
    signatures = _MAGIC_BYTES.get(ext)
    if not signatures:
        return True
    if not any(data.startswith(sig) for sig in signatures):
        return False
    if ext == ".webp" and data[8:12] != b"WEBP":
        return False
    return True


async def save_upload(db: Session, file: UploadFile | None, category: str, allowed_ext: set[str]) -> str:
    """Enregistre un fichier uploadé en base de données. Retourne le chemin
    logique (ex. "produits/<uuid>.jpg") à conserver dans la colonne du modèle
    appelant."""
    if file is None or not file.filename:
        raise ValueError("Aucun fichier fourni")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise ValueError(f"Extension non autorisée : {ext}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Fichier trop volumineux (max {settings.max_upload_size_mb} Mo)")
    if not _matches_magic_bytes(data, ext):
        raise ValueError("Le contenu du fichier ne correspond pas à son extension")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    logical_path = f"{category}/{stored_name}"
    content_type = mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
    db.add(models.StoredFile(path=logical_path, content_type=content_type, data=data))
    return logical_path


def get_stored_file(db: Session, logical_path: str | None) -> "models.StoredFile | None":
    if not logical_path:
        return None
    return db.query(models.StoredFile).filter(models.StoredFile.path == logical_path).first()


def delete_stored_file(db: Session, logical_path: str | None) -> None:
    stored = get_stored_file(db, logical_path)
    if stored:
        db.delete(stored)
