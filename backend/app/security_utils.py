"""Utilitaires de défense en profondeur pour les exports CSV et les en-têtes HTTP
construits à partir de texte saisi par un utilisateur."""

_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    """Neutralise l'injection de formule dans les exports CSV (CWE-1236) : si la
    cellule ouverte dans Excel/LibreOffice/Sheets commence par un caractère qui y
    déclenche l'évaluation d'une formule (=, +, -, @, tabulation), elle est préfixée
    d'une apostrophe pour forcer une interprétation en texte brut."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_TRIGGERS):
        return "'" + text
    return text


def safe_content_disposition(filename: str | None, fallback: str = "fichier") -> str:
    """Construit une valeur d'en-tête Content-Disposition sûre à partir d'un nom
    potentiellement fourni par l'utilisateur : retire les caractères de contrôle
    (injection d'en-tête HTTP) et échappe les guillemets."""
    text = (filename or "").strip()
    text = "".join(ch for ch in text if ch not in "\r\n\t" and ord(ch) >= 32)
    text = text.replace('"', "'")
    return text or fallback
