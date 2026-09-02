from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_owner

router = APIRouter(prefix="/api/coupons", tags=["coupons"], dependencies=[Depends(require_owner)])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format attendu AAAA-MM-JJ)")


def _get_owned_coupon(db: Session, shop: models.Shop, coupon_id: int) -> models.Coupon:
    coupon = (
        db.query(models.Coupon)
        .filter(models.Coupon.id == coupon_id, models.Coupon.shop_id == shop.id)
        .first()
    )
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code promo introuvable")
    return coupon


@router.get("", response_model=list[schemas.CouponOut])
def list_coupons(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return db.query(models.Coupon).filter(models.Coupon.shop_id == shop.id).order_by(models.Coupon.created_at.desc()).all()


@router.post("", response_model=schemas.CouponOut, status_code=status.HTTP_201_CREATED)
def create_coupon(payload: schemas.CouponIn, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    code = payload.code.strip().upper()
    existing = (
        db.query(models.Coupon)
        .filter(models.Coupon.shop_id == shop.id, models.Coupon.code == code)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code existe déjà")

    coupon = models.Coupon(
        shop_id=shop.id,
        code=code,
        type=payload.type,
        valeur=payload.valeur,
        date_debut=_parse_date(payload.date_debut),
        date_fin=_parse_date(payload.date_fin),
        usage_max=payload.usage_max,
        actif=payload.actif,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/{coupon_id}", response_model=schemas.CouponOut)
def update_coupon(
    coupon_id: int, payload: schemas.CouponIn,
    shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db),
):
    coupon = _get_owned_coupon(db, shop, coupon_id)
    code = payload.code.strip().upper()
    existing = (
        db.query(models.Coupon)
        .filter(models.Coupon.shop_id == shop.id, models.Coupon.code == code, models.Coupon.id != coupon_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce code existe déjà")

    coupon.code = code
    coupon.type = payload.type
    coupon.valeur = payload.valeur
    coupon.date_debut = _parse_date(payload.date_debut)
    coupon.date_fin = _parse_date(payload.date_fin)
    coupon.usage_max = payload.usage_max
    coupon.actif = payload.actif
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(coupon_id: int, shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    coupon = _get_owned_coupon(db, shop, coupon_id)
    db.delete(coupon)
    db.commit()


def validate_and_apply_coupon(db: Session, shop_id: int, code: str, sous_total: float) -> tuple[models.Coupon, float]:
    """Valide un code promo et calcule la réduction correspondante — utilisé à la
    fois par la création de commande interne et par la boutique publique, pour ne
    pas dupliquer la logique de calcul à deux endroits (leçon tirée du bug promo
    prix_promo/effective_price, voir la mémoire du projet)."""
    coupon = (
        db.query(models.Coupon)
        .filter(models.Coupon.shop_id == shop_id, models.Coupon.code == code.strip().upper())
        .first()
    )
    if coupon is None or not coupon.actif:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code promo invalide")
    today = date.today()
    if coupon.date_debut and today < coupon.date_debut:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce code promo n'est pas encore actif")
    if coupon.date_fin and today > coupon.date_fin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce code promo a expiré")
    if coupon.usage_max is not None and coupon.usage_compte >= coupon.usage_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce code promo a atteint sa limite d'utilisation")

    if coupon.type == models.CouponType.POURCENTAGE:
        discount = sous_total * coupon.valeur / 100
    else:
        discount = coupon.valeur
    discount = min(discount, sous_total)

    coupon.usage_compte += 1
    return coupon, discount
