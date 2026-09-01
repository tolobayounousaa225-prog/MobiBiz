"""Migrations idempotentes exécutées à chaque démarrage de l'application — sans
dépendance à un outil de migration externe. Chaque étape se protège elle-même par
une vérification d'état avant d'agir, donc elle n'a plus aucun effet après son
premier passage réussi. Nécessaire dès qu'une table existe déjà en production :
Base.metadata.create_all() ne fait jamais d'ALTER TABLE sur une table existante."""

import logging

from sqlalchemy import inspect, text

from .database import Base, engine

logger = logging.getLogger("mobibiz.migrations")


def _backfill_shop_slugs() -> None:
    from .database import SessionLocal
    from .slug_utils import generate_unique_shop_slug

    db = SessionLocal()
    try:
        from . import models

        shops_sans_slug = db.query(models.Shop).filter(
            (models.Shop.slug.is_(None)) | (models.Shop.slug == "")
        ).all()
        for shop in shops_sans_slug:
            shop.slug = generate_unique_shop_slug(db, shop.nom)
        if shops_sans_slug:
            db.commit()
            logger.info("Slug généré pour %d boutique(s) existante(s).", len(shops_sans_slug))
    finally:
        db.close()


def run_startup_migrations() -> None:
    inspector = inspect(engine)

    if inspector.has_table("shops"):
        columns = {c["name"] for c in inspector.get_columns("shops")}
        if "wave_payment_link" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shops ADD COLUMN wave_payment_link VARCHAR(500)"))
            logger.info("Colonne wave_payment_link ajoutée à shops.")
        if "slug" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shops ADD COLUMN slug VARCHAR(180)"))
            logger.info("Colonne slug ajoutée à shops.")
        if "boutique_publique_active" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shops ADD COLUMN boutique_publique_active BOOLEAN DEFAULT FALSE"))
            logger.info("Colonne boutique_publique_active ajoutée à shops.")

    if inspector.has_table("users"):
        columns = {c["name"] for c in inspector.get_columns("users")}
        if "shop_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN shop_id INTEGER"))
            logger.info("Colonne shop_id ajoutée à users.")
        if "employee_role" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN employee_role VARCHAR(20)"))
            logger.info("Colonne employee_role ajoutée à users.")

    Base.metadata.create_all(bind=engine)

    if inspector.has_table("shops"):
        _backfill_shop_slugs()

    # Contrainte d'unicité posée après coup (une fois tous les slugs backfillés) —
    # jamais directement dans l'ALTER TABLE ci-dessus, qui tournerait avant le
    # backfill et échouerait sur les valeurs NULL/dupliquées d'une base existante.
    inspector = inspect(engine)
    if inspector.has_table("shops"):
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("shops")}
        existing_constraints = {c["name"] for c in inspector.get_unique_constraints("shops")}
        if "ix_shops_slug" not in existing_indexes and "shops_slug_key" not in existing_constraints:
            with engine.begin() as conn:
                conn.execute(text("CREATE UNIQUE INDEX ix_shops_slug ON shops (slug)"))
            logger.info("Index unique posé sur shops.slug.")
