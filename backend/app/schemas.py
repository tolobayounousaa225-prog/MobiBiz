from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import OrderStatus, PaiementStatut, UserRole


# ---------- Auth ----------
class RegisterIn(BaseModel):
    nom: str
    prenom: str
    telephone: str
    email: EmailStr | None = None
    password: str = Field(min_length=6)
    boutique_nom: str


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


class ShopOut(ShopIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    created_at: datetime


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
    image_url: str | None = None
    actif: bool = True


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    shop_id: int
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
    quantite: int = Field(gt=0)


class OrderIn(BaseModel):
    customer_id: int | None = None
    nouveau_client: CustomerIn | None = None
    items: list[OrderItemIn]
    reduction: float = Field(ge=0, default=0)
    frais_livraison: float = Field(ge=0, default=0)
    notes: str | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    quantite: int
    prix_unitaire: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: str
    customer_id: int
    customer_nom: str | None = None
    reduction: float
    frais_livraison: float
    total: float
    statut: OrderStatus
    paiement_statut: PaiementStatut
    notes: str | None = None
    created_at: datetime
    items: list[OrderItemOut] = []


class OrderStatusIn(BaseModel):
    statut: OrderStatus


class PaiementStatutIn(BaseModel):
    paiement_statut: PaiementStatut


# ---------- Stock ----------
class StockAdjustIn(BaseModel):
    quantite: int
    motif: str | None = None


# ---------- Dashboard ----------
class DashboardOut(BaseModel):
    chiffre_affaires: float
    nombre_commandes: int
    nombre_clients: int
    nombre_produits: int
    benefice_estime: float
    impayes: float
    produits_stock_faible: int
