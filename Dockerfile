FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-prod.txt backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY backend/ .

EXPOSE 8000

# Forme shell (pas exec) pour permettre l'expansion de $PORT — Railway assigne
# dynamiquement son propre port via cette variable.
# --proxy-headers --forwarded-allow-ips="*" : sans ça, request.client.host vaut
# l'IP interne du proxy Railway (instable d'une requête à l'autre en pratique),
# jamais celle du vrai visiteur — ce qui rendait tout le rate-limiting par IP
# (login, reset mot de passe, commande/avis publics, vérification de reçus)
# inopérant en production (confirmé : 13 tentatives de connexion rapprochées
# sans jamais déclencher le 429 attendu après 8). Le conteneur n'étant jamais
# exposé directement (seul Railway peut s'y connecter), faire confiance à
# X-Forwarded-For pour n'importe quel pair direct revient à ne faire confiance
# qu'à Railway lui-même.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*"
