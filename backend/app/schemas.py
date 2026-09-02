from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AdminRole,
    CouponType,
    DeliveryMode,
    EmployeeRole,
    ExpenseCategory,
    NotificationType,
    OrderStatus,
    PaiementStatut,
    SubscriptionPlan,
    SubscriptionStatus,
    TicketStatus,
    UserRole,
)

# Questions de sécurité prédéfinies (pas de champ libre, pour éviter des
# questions/réponses trop faibles ou triviales à deviner).
SECURITY_QUESTIONS = [
    "Quel est le nom de votre premier animal de compagnie ?",
    "Quel est le nom de votre ville natale ?",
    "Quel est le prénom de votre mère ?",
    "Quel est le nom de votre école primaire ?",
    "Quel est votre plat préféré ?",
]


# ---------- Auth ----------
class RegisterIn(BaseModel):
    nom: str
    prenom: str
    telephone: str
    email: EmailStr | None = None
    password: str = Field(min_length=6)
    boutique_nom: str
    security_question: str
    security_answer: str = Field(min_length=2)
    referral_code: str | None = None


class LoginIn(BaseModel):
    telephone: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    prenom: str
    telephone: str
    email: EmailStr | None = None
    role: UserRole
    employee_role: EmployeeRole | None = None
    admin_role: AdminRole | None = None
    has_security_question: bool = False


class SecurityQuestionUpdateIn(BaseModel):
    security_question: str
    security_answer: str = Field(min_length=2)


class PasswordChangeIn(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str = Field(min_length=6)


class ForgotPasswordQuestionIn(BaseModel):
    telephone: str


class ForgotPasswordQuestionOut(BaseModel):
    question: str


class ForgotPasswordResetIn(BaseModel):
    telephone: str
    reponse: str
    nouveau_mot_de_passe: str = Field(min_length=6)


# ---------- Shop ----------
class ShopIn(BaseModel):
    nom: str
    description: str | None = None
    telephone: str | None = None
    whatsapp: str | None = None
    adresse: str | None = None
    commune: str | None = None
    logo_url: str | None = None
    wave_payment_link: str | None = None
    boutique_publique_active: bool = False


class ShopOut(ShopIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    slug: str
    abonnement_statut: SubscriptionStatus
    abonnement_plan: SubscriptionPlan
    prochain_paiement_le: date_type | None = None
    essai_expire_le: date_type | None = None
    referral_code: str
    nombre_parrainages: int = 0
    created_at: datetime


class ShopPlanChangeIn(BaseModel):
    abonnement_plan: SubscriptionPlan


# ---------- Category ----------
class CategoryIn(BaseModel):
    nom: str


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Product ----------
class ProductIn(BaseModel):
    nom: str
    description: str | None = None
    reference: str | None = None
    category_id: int | None = None
    prix_achat: float = Field(ge=0, default=0)
    prix_vente: float = Field(ge=0, default=0)
    stock: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=5)
    actif: bool = True
    prix_promo: float | None = Field(ge=0, default=None)
    promo_actif: bool = False
    has_variants: bool = False


class ProductVariantIn(BaseModel):
    nom: str = Field(min_length=1, max_length=150)
    sku: str | None = None
    prix_vente: float = Field(ge=0)
    stock: int = Field(ge=0, default=0)
    actif: bool = True


class ProductVariantOut(ProductVariantIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    created_at: datetime


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_url: str
    ordre: int


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shop_id: int
    image_url: str | None = None
    variants: list[ProductVariantOut] = []
    images: list[ProductImageOut] = []
    created_at: datetime


# ---------- Customer ----------
class CustomerIn(BaseModel):
    nom: str
    telephone: str | None = None
    email: str | None = None
    adresse: str | None = None
    commune: str | None = None


class CustomerOut(CustomerIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shop_id: int
    created_at: datetime


class CustomerStats(CustomerOut):
    total_achats: float = 0
    nombre_commandes: int = 0
    derniere_commande: datetime | None = None
    segment: str = "nouveau"


# ---------- Orders ----------
class OrderItemIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantite: int = Field(gt=0)


class OrderIn(BaseModel):
    customer_id: int | None = None
    nouveau_client: CustomerIn | None = None
    items: list[OrderItemIn]
    reduction: float = Field(ge=0, default=0)
    frais_livraison: float = Field(ge=0, default=0)
    coupon_code: str | None = None
    notes: str | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    variant_id: int | None = None
    variant_nom: str | None = None
    quantite: int
    prix_unitaire: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: str
    customer_id: int
    customer_nom: str | None = None
    customer_telephone: str | None = None
    coupon_code: str | None = None
    reduction: float
    frais_livraison: float
    total: float
    statut: OrderStatus
    paiement_statut: PaiementStatut
    notes: str | None = None
    mode_livraison: DeliveryMode | None = None
    livreur_nom: str | None = None
    adresse_livraison: str | None = None
    commune_livraison: str | None = None
    heure_livraison_prevue: datetime | None = None
    preuve_livraison: str | None = None
    created_at: datetime
    items: list[OrderItemOut] = []


class OrderStatusIn(BaseModel):
    statut: OrderStatus


class PaiementStatutIn(BaseModel):
    paiement_statut: PaiementStatut


class DeliveryUpdateIn(BaseModel):
    mode_livraison: DeliveryMode | None = None
    livreur_nom: str | None = None
    adresse_livraison: str | None = None
    commune_livraison: str | None = None
    heure_livraison_prevue: datetime | None = None
    preuve_livraison: str | None = None


# ---------- Coupons ----------
class CouponIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    type: CouponType
    valeur: float = Field(gt=0)
    date_debut: str | None = None  # ISO yyyy-mm-dd
    date_fin: str | None = None
    usage_max: int | None = Field(gt=0, default=None)
    actif: bool = True


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    type: CouponType
    valeur: float
    date_debut: date_type | None = None
    date_fin: date_type | None = None
    usage_max: int | None = None
    usage_compte: int
    actif: bool
    created_at: datetime


# ---------- Avis clients ----------
class ProductReviewIn(BaseModel):
    nom_client: str = Field(min_length=2, max_length=150)
    note: int = Field(ge=1, le=5)
    commentaire: str | None = Field(default=None, max_length=1000)


class ProductReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    nom_client: str
    note: int
    commentaire: str | None = None
    approuve: bool
    created_at: datetime


class ProductReviewSummaryOut(BaseModel):
    moyenne: float | None = None
    total: int
    avis: list[ProductReviewOut]


# ---------- Stock ----------
class StockAdjustIn(BaseModel):
    quantite: int
    motif: str | None = None


class ProductSalesStat(BaseModel):
    product_id: int
    nom: str
    stock: int
    quantite_vendue: int
    chiffre_affaires: float
    valeur_stock: float


class StockStatsOut(BaseModel):
    valeur_stock_achat: float
    valeur_stock_vente: float
    benefice_potentiel: float
    rotation_globale: float | None = None
    produits_plus_vendus: list[ProductSalesStat]
    produits_moins_vendus: list[ProductSalesStat]
    stock_dormant: list[ProductSalesStat]


# ---------- Dashboard ----------
class DashboardOut(BaseModel):
    chiffre_affaires: float
    nombre_commandes: int
    nombre_clients: int
    nombre_produits: int
    benefice_estime: float
    impayes: float
    produits_stock_faible: int


# ---------- Employés ----------
class EmployeeIn(BaseModel):
    nom: str
    prenom: str
    telephone: str
    password: str = Field(min_length=6)
    employee_role: EmployeeRole


class EmployeeUpdateIn(BaseModel):
    employee_role: EmployeeRole
    actif: bool = True


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    prenom: str
    telephone: str
    employee_role: EmployeeRole | None = None
    actif: bool
    created_at: datetime


# ---------- Dépenses ----------
class ExpenseIn(BaseModel):
    categorie: ExpenseCategory
    libelle: str
    montant: float = Field(ge=0)
    date: str  # ISO yyyy-mm-dd


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    categorie: ExpenseCategory
    libelle: str
    montant: float
    date: object
    created_at: datetime


class FinanceSummaryOut(BaseModel):
    chiffre_affaires: float
    cout_produits: float
    depenses: float
    benefice: float


# ---------- Notifications ----------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: NotificationType
    message: str
    order_id: int | None = None
    lu: bool
    created_at: datetime


# ---------- Boutique publique ----------
class PublicProductVariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    prix_vente: float
    stock: int


class PublicProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    description: str | None = None
    prix_vente: float
    prix_promo: float | None = None
    promo_actif: bool = False
    image_url: str | None = None
    stock: int
    category_id: int | None = None
    has_variants: bool = False
    variants: list[PublicProductVariantOut] = []
    images: list[ProductImageOut] = []
    note_moyenne: float | None = None
    nombre_avis: int = 0


class PublicShopOut(BaseModel):
    nom: str
    description: str | None = None
    telephone: str | None = None
    whatsapp: str | None = None
    adresse: str | None = None
    commune: str | None = None
    logo_url: str | None = None
    produits: list[PublicProductOut]
    categories: list[CategoryOut]


class PublicOrderItemIn(BaseModel):
    product_id: int
    variant_id: int | None = None
    quantite: int = Field(gt=0)


class PublicOrderIn(BaseModel):
    client_nom: str
    client_telephone: str
    client_commune: str | None = None
    items: list[PublicOrderItemIn]
    coupon_code: str | None = None
    notes: str | None = None


class PublicOrderOut(BaseModel):
    numero: str
    total: float


# ---------- Administration plateforme ----------
class AdminShopOut(BaseModel):
    id: int
    nom: str
    slug: str
    abonnement_statut: SubscriptionStatus
    abonnement_plan: SubscriptionPlan
    prochain_paiement_le: str | None = None
    essai_expire_le: str | None = None
    proprietaire_nom: str
    proprietaire_telephone: str
    nombre_produits: int
    nombre_commandes: int
    chiffre_affaires: float
    created_at: datetime


class AdminShopStatusIn(BaseModel):
    abonnement_statut: SubscriptionStatus


class AdminShopPlanIn(BaseModel):
    abonnement_plan: SubscriptionPlan


class AdminStatsOut(BaseModel):
    boutiques_total: int
    boutiques_actives: int
    boutiques_suspendues: int
    boutiques_essai: int
    utilisateurs_total: int
    commandes_total: int
    chiffre_affaires_total: float
    parrainages_total: int = 0


class AdminBulkStatusIn(BaseModel):
    shop_ids: list[int] = Field(min_length=1)
    abonnement_statut: SubscriptionStatus


class AdminBulkActionOut(BaseModel):
    mis_a_jour: int
    boutiques: list[str]


class SubscriptionPaymentIn(BaseModel):
    montant: float = Field(gt=0)
    date_paiement: str  # ISO yyyy-mm-dd


class SubscriptionPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    montant: float
    date_paiement: date_type
    created_at: datetime


class PlatformSettingsIn(BaseModel):
    wave_payment_link: str | None = None


class PlatformSettingsOut(BaseModel):
    wave_payment_link: str | None = None


class AdminUserOut(BaseModel):
    id: int
    nom: str
    prenom: str
    telephone: str
    role: UserRole
    employee_role: EmployeeRole | None = None
    actif: bool
    boutique_nom: str | None = None
    created_at: datetime


# ---------- Journal d'audit ----------
class AuditLogOut(BaseModel):
    id: int
    admin_nom: str
    action: str
    cible_type: str
    cible_id: int | None = None
    details: str | None = None
    created_at: datetime


# ---------- Support / tickets ----------
class TicketCreateIn(BaseModel):
    sujet: str = Field(min_length=3)
    message: str = Field(min_length=3)


class TicketMessageIn(BaseModel):
    message: str = Field(min_length=1)


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    auteur_id: int
    auteur_nom: str
    auteur_role: UserRole
    message: str
    created_at: datetime


class TicketOut(BaseModel):
    id: int
    sujet: str
    statut: TicketStatus
    boutique_nom: str | None = None
    created_at: datetime
    messages: list[TicketMessageOut] = []


class TicketStatusIn(BaseModel):
    statut: TicketStatus


# ---------- Comptes admin ----------
class AdminCreateIn(BaseModel):
    nom: str
    prenom: str
    telephone: str
    password: str = Field(min_length=6)
    admin_role: AdminRole = AdminRole.SUPPORT


class AdminAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    prenom: str
    telephone: str
    admin_role: AdminRole | None = None
    actif: bool
    created_at: datetime


# ---------- Notifications admin ----------
class AdminNotificationsOut(BaseModel):
    tickets_ouverts: int
    paiements_en_retard: int
    nouvelles_boutiques_7j: int
    essais_expirant_bientot: int


# ---------- Revenus plateforme ----------
class PlanRepartitionOut(BaseModel):
    plan: SubscriptionPlan
    nombre: int


class PlatformRevenueOut(BaseModel):
    mrr_estime: float
    total_encaisse: float
    encaisse_mois_courant: float
    repartition_plans: list[PlanRepartitionOut]


# ---------- Connexion en tant que ----------
class ImpersonateOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    boutique_nom: str


# ---------- Plans ----------
class PlanOut(BaseModel):
    id: SubscriptionPlan
    nom: str
    prix_mensuel: int | None = None
    max_produits: int | None = None
    max_employes: int | None = None
    boutique_publique: bool
    avantages: list[str]


# ---------- Statistiques d'évolution ----------
class MonthlyStatOut(BaseModel):
    mois: str  # "2026-09"
    nouvelles_boutiques: int
    commandes: int
    chiffre_affaires: float
