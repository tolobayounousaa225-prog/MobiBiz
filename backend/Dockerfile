FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

EXPOSE 8000

# Forme shell (pas exec) pour permettre l'expansion de $PORT — Railway assigne
# dynamiquement son propre port via cette variable.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
