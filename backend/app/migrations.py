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


def _add_columns_if_missing(inspector, table: str, columns_sql: dict[str, str]) -> None:
    """columns_sql: {nom_colonne: fragment DDL apres le nom, ex. "VARCHAR(20)"}."""
    if not inspector.has_table(table):
        return
    existing = {c["name"] for c in inspector.get_columns(table)}
    for name, ddl in columns_sql.items():
        if name not in existing:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            logger.info("Colonne %s ajoutée à %s.", name, table)


def _ensure_enum_value(pg_enum_name: str, value: str) -> None:
    """Ajoute une valeur à un type ENUM Postgres déjà créé — nécessaire quand un
    membre est ajouté à un `enum.Enum` Python *après* que la table qui l'utilise
    a déjà été créée en production : `Base.metadata.create_all()` crée le TYPE une
    seule fois et ne le modifie jamais ensuite, contrairement à SQLite (utilisé en
    dev local) qui ne fait aucune vérification stricte de type ENUM — d'où un bug
    invisible en local mais bloquant en production (`invalid input value for enum`).
    `ADD VALUE IF NOT EXISTS` doit tourner en dehors d'un bloc de transaction
    explicite sur Postgres, d'où l'isolation AUTOCOMMIT plutôt que engine.begin()."""
    if engine.dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f"ALTER TYPE {pg_enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


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

    _add_columns_if_missing(inspector, "shops", {
        "abonnement_statut": "VARCHAR(20) DEFAULT 'ACTIF'",
        "abonnement_plan": "VARCHAR(20) DEFAULT 'FREE'",
        "prochain_paiement_le": "DATE",
    })

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

    _add_columns_if_missing(inspector, "users", {
        "security_question": "VARCHAR(255)",
        "security_answer_hash": "VARCHAR(255)",
    })

    # UserRole.EMPLOYEE a été ajouté après la création initiale de la table users
    # (V1 n'avait que ADMIN/OWNER) — le type ENUM Postgres doit être mis à jour
    # explicitement, sinon toute tentative de créer un employé échoue en
    # production avec "invalid input value for enum userrole: EMPLOYEE".
    _ensure_enum_value("userrole", "EMPLOYEE")

    _add_columns_if_missing(inspector, "products", {
        "prix_promo": "FLOAT",
        "promo_actif": "BOOLEAN DEFAULT FALSE",
        "image_path": "VARCHAR(300)",
    })
    _add_columns_if_missing(inspector, "orders", {
        "mode_livraison": "VARCHAR(20)",
        "livreur_nom": "VARCHAR(150)",
        "adresse_livraison": "VARCHAR(255)",
        "commune_livraison": "VARCHAR(120)",
        "heure_livraison_prevue": "TIMESTAMP",
        "preuve_livraison": "TEXT",
    })

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
