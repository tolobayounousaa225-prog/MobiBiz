import enum
from datetime import date as date_type
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime) -> datetime:
    """SQLite drops tzinfo on stored datetimes even for a DateTime(timezone=True)
    column, so a value read back can be naive while now_utc() is always aware.
    Treat a naive value as UTC (the only timezone ever written) before comparing."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class StoredFile(Base):
    """Fichier uploadé (photo produit...) stocké en base de données plutôt que sur
    le disque du conteneur — Railway ne fournit pas de disque persistant, il est
    réinitialisé à chaque déploiement (même problème et même correctif que sur
    LECIM, voir la mémoire "lecim_file_storage_architecture"). `path` sert de clé
    logique (ex. "produits/<uuid>.jpg")."""

    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(300), unique=True, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OWNER = "owner"
    EMPLOYEE = "employee"


class EmployeeRole(str, enum.Enum):
    MANAGER = "manager"
    VENDEUR = "vendeur"
    MAGASINIER = "magasinier"
    COMPTABLE = "comptable"


# Matrice des droits par rôle (section 24 du cahier des charges) : modules avec
# accès complet (lecture + écriture) pour chaque rôle employé. Le propriétaire a
# toujours accès à tout, indépendamment de cette table.
EMPLOYEE_MODULE_ACCESS: dict["EmployeeRole", set[str]] = {
    EmployeeRole.MANAGER: {"produits", "commandes", "stock"},
    EmployeeRole.VENDEUR: {"commandes"},
    EmployeeRole.MAGASINIER: {"stock"},
    EmployeeRole.COMPTABLE: {"finance"},
}


class ExpenseCategory(str, enum.Enum):
    ACHATS = "achats"
    TRANSPORT = "transport"
    PUBLICITE = "publicite"
    EMBALLAGE = "emballage"
    SALAIRES = "salaires"
    AUTRES = "autres"


class NotificationType(str, enum.Enum):
    NOUVELLE_COMMANDE = "nouvelle_commande"
    STOCK_FAIBLE = "stock_faible"
    PAIEMENT_RECU = "paiement_recu"


class DeliveryMode(str, enum.Enum):
    INTERNE = "interne"
    PARTENAIRE = "partenaire"
    RETRAIT_BOUTIQUE = "retrait_boutique"


class SubscriptionStatus(str, enum.Enum):
    ESSAI = "essai"
    ACTIF = "actif"
    SUSPENDU = "suspendu"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class OrderStatus(str, enum.Enum):
    NOUVELLE = "nouvelle"
    CONFIRMEE = "confirmee"
    EN_PREPARATION = "en_preparation"
    EXPEDIEE = "expediee"
    LIVREE = "livree"
    TERMINEE = "terminee"
    ANNULEE = "annulee"
    RETOURNEE = "retournee"
    ECHOUEE = "echouee"


class PaiementStatut(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    INITIE = "initie"
    PAYE = "paye"
    ECHOUE = "echoue"


class StockMovementType(str, enum.Enum):
    VENTE = "vente"
    REAPPRO = "reappro"
    AJUSTEMENT = "ajustement"
    ANNULATION = "annulation"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120))
    telephone: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.OWNER)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    # Uniquement pour role == EMPLOYEE : boutique et rôle métier de l'employé.
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"), nullable=True, index=True)
    employee_role: Mapped[EmployeeRole | None] = mapped_column(Enum(EmployeeRole), nullable=True)
    # Permet la réinitialisation du mot de passe par l'utilisateur lui-même sans
    # SMS/email (aucun service tiers configuré) — nullable car absent pour les
    # comptes créés avant l'introduction de cette fonctionnalité, ou pour un
    # employé qui ne l'a pas encore définie depuis son premier login.
    security_question: Mapped[str | None] = mapped_column(String(255), nullable=True)
    security_answer_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shops: Mapped[list["Shop"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", foreign_keys="Shop.owner_id"
    )

    @property
    def has_security_question(self) -> bool:
        return bool(self.security_question and self.security_answer_hash)

    def has_module_access(self, module: str) -> bool:
        if self.role == UserRole.OWNER:
            return True
        if self.role == UserRole.EMPLOYEE and self.employee_role:
            return module in EMPLOYEE_MODULE_ACCESS.get(self.employee_role, set())
        return False


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    nom: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commune: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wave_payment_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    boutique_publique_active: Mapped[bool] = mapped_column(Boolean, default=False)
    abonnement_statut: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIF)
    abonnement_plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    prochain_paiement_le: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    owner: Mapped["User"] = relationship(back_populates="shops", foreign_keys=[owner_id])
    categories: Mapped[list["Category"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    customers: Mapped[list["Customer"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="shop", cascade="all, delete-orphan")
    abonnement_paiements: Mapped[list["SubscriptionPayment"]] = relationship(back_populates="shop", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    nom: Mapped[str] = mapped_column(String(120))

    shop: Mapped["Shop"] = relationship(back_populates="categories")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    nom: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prix_achat: Mapped[float] = mapped_column(Float, default=0)
    prix_vente: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    seuil_alerte: Mapped[int] = mapped_column(Integer, default=5)
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    prix_promo: Mapped[float | None] = mapped_column(Float, nullable=True)
    promo_actif: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="products")
    category: Mapped["Category | None"] = relationship(back_populates="products")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    @property
    def image_url(self) -> str | None:
        return f"/api/produits/{self.id}/image" if self.image_path else None

    @property
    def effective_price(self) -> float:
        if self.promo_actif and self.prix_promo is not None:
            return self.prix_promo
        return self.prix_vente


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    nom: Mapped[str] = mapped_column(String(150))
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commune: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="customers")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    numero: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    reduction: Mapped[float] = mapped_column(Float, default=0)
    frais_livraison: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    statut: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NOUVELLE)
    paiement_statut: Mapped[PaiementStatut] = mapped_column(Enum(PaiementStatut), default=PaiementStatut.EN_ATTENTE)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode_livraison: Mapped[DeliveryMode | None] = mapped_column(Enum(DeliveryMode), nullable=True)
    livreur_nom: Mapped[str | None] = mapped_column(String(150), nullable=True)
    adresse_livraison: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commune_livraison: Mapped[str | None] = mapped_column(String(120), nullable=True)
    heure_livraison_prevue: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preuve_livraison: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="orders")
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def customer_nom(self) -> str | None:
        return self.customer.nom if self.customer else None

    @property
    def customer_telephone(self) -> str | None:
        return self.customer.telephone if self.customer else None


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[float] = mapped_column(Float)
    prix_achat_unitaire: Mapped[float] = mapped_column(Float, default=0)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    type: Mapped[StockMovementType] = mapped_column(Enum(StockMovementType))
    quantite: Mapped[int] = mapped_column(Integer)
    motif: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    product: Mapped["Product"] = relationship(back_populates="stock_movements")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    categorie: Mapped[ExpenseCategory] = mapped_column(Enum(ExpenseCategory))
    libelle: Mapped[str] = mapped_column(String(255))
    montant: Mapped[float] = mapped_column(Float)
    date: Mapped[date_type] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="expenses")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    message: Mapped[str] = mapped_column(String(500))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    lu: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="notifications")


class SubscriptionPayment(Base):
    """Un paiement d'abonnement plateforme enregistré manuellement par l'admin
    (confirmé après réception sur son Wave, pas d'API de paiement automatisée —
    même logique que le paiement Wave boutique -> client)."""

    __tablename__ = "subscription_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    montant: Mapped[float] = mapped_column(Float)
    date_paiement: Mapped[date_type] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    shop: Mapped["Shop"] = relationship(back_populates="abonnement_paiements")


class PlatformSettings(Base):
    """Ligne unique (id=1) de paramètres plateforme — pour l'instant seulement le
    lien de paiement Wave de l'administrateur, vers lequel les boutiques paient
    leur abonnement MobiBiz."""

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    wave_payment_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
