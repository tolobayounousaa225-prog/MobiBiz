"""Migrations idempotentes exécutées à chaque démarrage de l'application — sans
dépendance à un outil de migration externe. Chaque étape se protège elle-même par
une vérification d'état avant d'agir, donc elle n'a plus aucun effet après son
premier passage réussi. Nécessaire dès qu'une table existe déjà en production :
Base.metadata.create_all() ne fait jamais d'ALTER TABLE sur une table existante."""

import logging

from sqlalchemy import inspect, text

from .database import Base, engine

logger = logging.getLogger("mobibiz.migrations")


def run_startup_migrations() -> None:
    inspector = inspect(engine)

    if inspector.has_table("shops"):
        columns = {c["name"] for c in inspector.get_columns("shops")}
        if "wave_payment_link" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shops ADD COLUMN wave_payment_link VARCHAR(500)"))
            logger.info("Colonne wave_payment_link ajoutée à shops.")

    Base.metadata.create_all(bind=engine)
