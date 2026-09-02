from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import expire_trial_if_needed
from ..notifications import notify
from ..rate_limit import enforce_public_order_rate_limit, enforce_review_rate_limit
from .coupons import validate_and_apply_coupon
from .orders import _generate_order_number

router = APIRouter(prefix="/api/public/boutiques", tags=["boutique-publique"])


def _get_active_public_shop(db: Session, slug: str) -> models.Shop:
    shop = (
        db.query(models.Shop)
        .filter(models.Shop.slug == slug, models.Shop.boutique_publique_active.is_(True))
        .first()
    )
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boutique introuvable")
    expire_trial_if_needed(db, shop)
    if shop.abonnement_statut == models.SubscriptionStatus.SUSPENDU:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boutique introuvable")
    return shop


def _review_stats(db: Session, shop_id: int) -> dict[int, tuple[float, int]]:
    rows = (
        db.query(
            models.ProductReview.product_id,
            func.avg(models.ProductReview.note),
            func.count(models.ProductReview.id),
        )
        .filter(models.ProductReview.shop_id == shop_id, models.ProductReview.approuve.is_(True))
        .group_by(models.ProductReview.product_id)
        .all()
    )
    return {product_id: (round(float(avg), 1), int(count)) for product_id, avg, count in rows}


def _to_public_product(product: models.Product, stats: dict[int, tuple[float, int]]) -> schemas.PublicProductOut:
    moyenne, nombre = stats.get(product.id, (None, 0))
    return schemas.PublicProductOut(
        id=product.id, nom=product.nom, description=product.description,
        prix_vente=product.prix_vente, prix_promo=product.prix_promo, promo_actif=product.promo_actif,
        image_url=product.image_url, stock=product.stock, category_id=product.category_id,
        has_variants=product.has_variants,
        variants=[v for v in product.variants if v.actif] if product.has_variants else [],
        images=product.images,
        note_moyenne=moyenne, nombre_avis=nombre,
    )


@router.get("/{slug}", response_model=schemas.PublicShopOut)
def get_public_shop(slug: str, db: Session = Depends(get_db)):
    shop = _get_active_public_shop(db, slug)
    products = (
        db.query(models.Product)
        .filter(
            models.Product.shop_id == shop.id, models.Product.actif.is_(True),
            (models.Product.stock > 0) | (models.Product.has_variants.is_(True)),
        )
        .order_by(models.Product.nom)
        .all()
    )
    # Un produit à variantes peut avoir stock=0 au niveau produit tout en ayant des
    # variantes disponibles — ne le filtrer que si aucune variante active n'a de stock.
    products = [p for p in products if not p.has_variants or any(v.actif and v.stock > 0 for v in p.variants)]
    stats = _review_stats(db, shop.id)
    categories = db.query(models.Category).filter(models.Category.shop_id == shop.id).order_by(models.Category.nom).all()
    return schemas.PublicShopOut(
        nom=shop.nom,
        description=shop.description,
        telephone=shop.telephone,
        whatsapp=shop.whatsapp,
        adresse=shop.adresse,
        commune=shop.commune,
        logo_url=shop.logo_display_url,
        produits=[_to_public_product(p, stats) for p in products],
        categories=categories,
    )


@router.get("/{slug}/produits/{product_id}/avis", response_model=schemas.ProductReviewSummaryOut)
def list_public_reviews(slug: str, product_id: int, db: Session = Depends(get_db)):
    shop = _get_active_public_shop(db, slug)
    reviews = (
        db.query(models.ProductReview)
        .filter(
            models.ProductReview.shop_id == shop.id, models.ProductReview.product_id == product_id,
            models.ProductReview.approuve.is_(True),
        )
        .order_by(models.ProductReview.created_at.desc())
        .all()
    )
    moyenne = round(sum(r.note for r in reviews) / len(reviews), 1) if reviews else None
    return schemas.ProductReviewSummaryOut(moyenne=moyenne, total=len(reviews), avis=reviews)


@router.post("/{slug}/produits/{product_id}/avis", response_model=schemas.ProductReviewOut, status_code=status.HTTP_201_CREATED)
def submit_public_review(slug: str, product_id: int, payload: schemas.ProductReviewIn, request: Request, db: Session = Depends(get_db)):
    enforce_review_rate_limit(request)
    shop = _get_active_public_shop(db, slug)
    product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.shop_id == shop.id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")

    review = models.ProductReview(
        shop_id=shop.id, product_id=product.id,
        nom_client=payload.nom_client, note=payload.note, commentaire=payload.commentaire,
        approuve=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.post("/{slug}/commandes", response_model=schemas.PublicOrderOut, status_code=status.HTTP_201_CREATED)
def create_public_order(slug: str, payload: schemas.PublicOrderIn, request: Request, db: Session = Depends(get_db)):
    enforce_public_order_rate_limit(request)
    shop = _get_active_public_shop(db, slug)

    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La commande doit contenir au moins un produit")

    customer = (
        db.query(models.Customer)
        .filter(models.Customer.shop_id == shop.id, models.Customer.telephone == payload.client_telephone)
        .first()
    )
    if customer is None:
        customer = models.Customer(
            shop_id=shop.id,
            nom=payload.client_nom,
            telephone=payload.client_telephone,
            commune=payload.client_commune,
        )
        db.add(customer)
        db.flush()

    order = models.Order(
        shop_id=shop.id,
        customer_id=customer.id,
        numero=_generate_order_number(db, shop.id),
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    sous_total = 0.0
    for item in payload.items:
        product = (
            db.query(models.Product)
            .filter(models.Product.id == item.product_id, models.Product.shop_id == shop.id, models.Product.actif.is_(True))
            .first()
        )
        if product is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Produit {item.product_id} invalide")

        variant: models.ProductVariant | None = None
        if item.variant_id is not None:
            variant = (
                db.query(models.ProductVariant)
                .filter(models.ProductVariant.id == item.variant_id, models.ProductVariant.product_id == product.id)
                .first()
            )
            if variant is None or not variant.actif:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variante invalide pour « {product.nom} »")
        elif product.has_variants:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"« {product.nom} » nécessite le choix d'une variante")

        prix_unitaire = variant.prix_vente if variant else product.effective_price

        if variant:
            if variant.stock < item.quantite:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuffisant pour « {product.nom} » ({variant.nom}) (disponible : {variant.stock})",
                )
            variant.stock -= item.quantite
        else:
            if product.stock < item.quantite:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Stock insuffisant pour « {product.nom} » (disponible : {product.stock})",
                )
            stock_avant = product.stock
            product.stock -= item.quantite
            if product.stock <= product.seuil_alerte < stock_avant:
                notify(db, shop.id, models.NotificationType.STOCK_FAIBLE, f"Stock faible : « {product.nom} » (reste {product.stock})")

        db.add(models.StockMovement(product_id=product.id, type=models.StockMovementType.VENTE, quantite=-item.quantite))
        db.add(models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=variant.id if variant else None,
            quantite=item.quantite,
            prix_unitaire=prix_unitaire,
            prix_achat_unitaire=product.prix_achat,
        ))
        sous_total += prix_unitaire * item.quantite

    reduction = 0.0
    if payload.coupon_code:
        coupon, discount = validate_and_apply_coupon(db, shop.id, payload.coupon_code, sous_total)
        order.coupon_id = coupon.id
        reduction = discount

    order.reduction = reduction
    order.total = max(sous_total - reduction, 0)
    notify(
        db, shop.id, models.NotificationType.NOUVELLE_COMMANDE,
        f"Nouvelle commande {order.numero} de {customer.nom} (boutique publique) — {order.total:.0f} FCFA",
        order_id=order.id,
    )
    db.commit()

    return schemas.PublicOrderOut(numero=order.numero, total=order.total)
