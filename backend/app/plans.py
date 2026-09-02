"""Définition des plans d'abonnement (section 34 du cahier des charges) : prix,
avantages affichés au commerçant, et limites appliquées côté serveur. `None` =
illimité. Ajuster ici seul suffit à changer les limites partout (frontend et
routers lisent la même source via /api/plans)."""

from .models import SubscriptionPlan

PLAN_FEATURES: dict[SubscriptionPlan, dict] = {
    SubscriptionPlan.FREE: {
        "nom": "Free",
        "prix_mensuel": 0,
        "max_produits": 20,
        "max_employes": 0,
        "boutique_publique": False,
        "avantages": [
            "Jusqu'à 20 produits",
            "Gestion clients et commandes",
            "Tableau de bord",
        ],
    },
    SubscriptionPlan.STARTER: {
        "nom": "Starter",
        "prix_mensuel": 5000,
        "max_produits": 100,
        "max_employes": 2,
        "boutique_publique": True,
        "avantages": [
            "Jusqu'à 100 produits",
            "Boutique publique en ligne",
            "Jusqu'à 2 employés",
            "Import Excel/CSV",
        ],
    },
    SubscriptionPlan.PRO: {
        "nom": "Pro",
        "prix_mensuel": 15000,
        "max_produits": 500,
        "max_employes": 5,
        "boutique_publique": True,
        "avantages": [
            "Jusqu'à 500 produits",
            "Boutique publique en ligne",
            "Jusqu'à 5 employés",
            "Marketing et promotions",
            "Rapports financiers",
        ],
    },
    SubscriptionPlan.BUSINESS: {
        "nom": "Business",
        "prix_mensuel": 30000,
        "max_produits": None,
        "max_employes": 15,
        "boutique_publique": True,
        "avantages": [
            "Produits illimités",
            "Boutique publique en ligne",
            "Jusqu'à 15 employés",
            "Marketing et promotions",
            "Rapports financiers",
            "Support prioritaire",
        ],
    },
    SubscriptionPlan.ENTERPRISE: {
        "nom": "Enterprise",
        "prix_mensuel": None,  # sur devis
        "max_produits": None,
        "max_employes": None,
        "boutique_publique": True,
        "avantages": [
            "Tout illimité",
            "Accompagnement dédié",
            "Support prioritaire",
        ],
    },
}

TRIAL_DAYS = 14
PAYMENT_VALIDITY_DAYS = 30
REFERRAL_BONUS_DAYS = 7


def plan_limit(plan: SubscriptionPlan, key: str):
    return PLAN_FEATURES.get(plan, PLAN_FEATURES[SubscriptionPlan.FREE]).get(key)
