import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_attempts: dict[str, list[float]] = defaultdict(list)


def _enforce(bucket: str, key: str, max_attempts: int, window_seconds: int, message: str) -> None:
    now = time.time()
    window_start = now - window_seconds
    full_key = f"{bucket}:{key}"
    attempts = [t for t in _attempts[full_key] if t > window_start]
    if len(attempts) >= max_attempts:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    attempts.append(now)
    _attempts[full_key] = attempts


def enforce_login_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    _enforce("login", client_ip, max_attempts=8, window_seconds=300,
             message="Trop de tentatives de connexion. Réessayez plus tard.")


def enforce_password_reset_rate_limit(request: Request, telephone: str) -> None:
    """La réponse à une question de sécurité a beaucoup moins d'entropie qu'un
    mot de passe — limite stricte à la fois par IP (empêche de sonder beaucoup
    de numéros rapidement) et par numéro ciblé (empêche de bourrer les réponses
    possibles sur un seul compte depuis plusieurs IP)."""
    client_ip = request.client.host if request.client else "unknown"
    _enforce("password_reset_ip", client_ip, max_attempts=10, window_seconds=900,
             message="Trop de tentatives. Réessayez plus tard.")
    _enforce("password_reset_phone", telephone, max_attempts=5, window_seconds=900,
             message="Trop de tentatives pour ce numéro. Réessayez plus tard.")


def enforce_public_order_rate_limit(request: Request) -> None:
    """Anti-spam sur la création de commande publique (aucune authentification,
    donc n'importe qui peut appeler cette route et faire décrémenter un vrai
    stock) — limite par IP, plus permissive que le login puisque des achats
    légitimes rapprochés restent possibles."""
    client_ip = request.client.host if request.client else "unknown"
    _enforce("public_order", client_ip, max_attempts=15, window_seconds=600,
             message="Trop de commandes envoyées. Réessayez dans quelques minutes.")


def enforce_review_rate_limit(request: Request) -> None:
    """Anti-spam sur le dépôt d'avis produit public (aucune authentification) —
    plus strict que les commandes, un avis n'a pas besoin d'être aussi fréquent
    qu'un achat légitime."""
    client_ip = request.client.host if request.client else "unknown"
    _enforce("public_review", client_ip, max_attempts=5, window_seconds=600,
             message="Trop d'avis envoyés. Réessayez dans quelques minutes.")


def enforce_verification_rate_limit(request: Request) -> None:
    """Limite le scan/l'interrogation répétée de la vérification publique de
    reçus (aucune authentification) — assez permissif pour qu'un client ou un
    vendeur scanne plusieurs reçus différents sans blocage, mais empêche de
    parcourir systématiquement les numéros de commande à la recherche de fuites."""
    client_ip = request.client.host if request.client else "unknown"
    _enforce("verification", client_ip, max_attempts=30, window_seconds=600,
             message="Trop de vérifications. Réessayez dans quelques minutes.")
