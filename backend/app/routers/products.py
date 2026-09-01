import csv
import io

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db
from ..deps import get_current_shop, require_any_module, require_module

router = APIRouter(prefix="/api/produits", tags=["produits"])

IMPORT_COLUMNS = ["nom", "reference", "categorie", "prix_achat", "prix_vente", "stock", "seuil_alerte"]


def _get_owned_product(db: Session, shop: models.Shop, product_id: int) -> models.Product:
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.shop_id == shop.id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produit introuvable")
    return product


@router.get("", response_model=list[schemas.ProductOut])
def list_products(
    q: str | None = None,
    category_id: int | None = None,
    stock_faible: bool = False,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_any_module("produits", "commandes", "stock")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Product).filter(models.Product.shop_id == shop.id)
    if q:
        query = query.filter(models.Product.nom.ilike(f"%{q}%"))
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if stock_faible:
        query = query.filter(models.Product.stock <= models.Product.seuil_alerte)
    return query.order_by(models.Product.nom).all()


@router.post("", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: schemas.ProductIn,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    if payload.category_id is not None:
        category = (
            db.query(models.Category)
            .filter(models.Category.id == payload.category_id, models.Category.shop_id == shop.id)
            .first()
        )
        if category is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Catégorie invalide")

    product = models.Product(shop_id=shop.id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/modele.csv")
def download_import_template(_: models.User = Depends(require_module("produits"))):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(IMPORT_COLUMNS)
    writer.writerow(["Robe rouge", "REF001", "Vêtements", "5000", "9000", "20", "5"])
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="modele_import_produits.csv"'},
    )


def _get_or_create_category(db: Session, shop: models.Shop, nom: str, cache: dict[str, models.Category]) -> models.Category:
    key = nom.strip().lower()
    if key in cache:
        return cache[key]
    category = (
        db.query(models.Category)
        .filter(models.Category.shop_id == shop.id, models.Category.nom.ilike(nom.strip()))
        .first()
    )
    if category is None:
        category = models.Category(shop_id=shop.id, nom=nom.strip())
        db.add(category)
        db.flush()
    cache[key] = category
    return category


def _parse_import_rows(filename: str, content: bytes) -> list[dict]:
    rows: list[dict] = []
    if filename.lower().endswith(".xlsx"):
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            headers = [str(h or "").strip().lower() for h in next(rows_iter)]
        except StopIteration:
            return []
        for raw in rows_iter:
            if raw is None or all(v is None for v in raw):
                continue
            rows.append({headers[i]: raw[i] for i in range(min(len(headers), len(raw)))})
    else:
        text = content.decode("utf-8-sig", errors="replace")
        delimiter = ";" if text.split("\n", 1)[0].count(";") >= text.split("\n", 1)[0].count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for raw in reader:
            rows.append({(k or "").strip().lower(): v for k, v in raw.items()})
    return rows


@router.post("/import")
async def import_products(
    file: UploadFile,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Format non supporté (CSV ou XLSX attendu)")

    content = await file.read()
    try:
        rows = _parse_import_rows(file.filename, content)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier illisible")

    category_cache: dict[str, models.Category] = {}
    crees = 0
    erreurs: list[dict] = []

    for i, row in enumerate(rows, start=2):  # ligne 1 = en-têtes
        nom = str(row.get("nom") or "").strip()
        if not nom:
            erreurs.append({"ligne": i, "message": "Nom manquant"})
            continue
        try:
            prix_achat = float(str(row.get("prix_achat") or 0).replace(",", "."))
            prix_vente = float(str(row.get("prix_vente") or 0).replace(",", "."))
            stock = int(float(str(row.get("stock") or 0).replace(",", ".")))
            seuil_alerte = int(float(str(row.get("seuil_alerte") or 5).replace(",", ".")))
        except ValueError:
            erreurs.append({"ligne": i, "message": "Valeur numérique invalide (prix, stock ou seuil)"})
            continue

        categorie_nom = str(row.get("categorie") or "").strip()
        category_id = None
        if categorie_nom:
            category_id = _get_or_create_category(db, shop, categorie_nom, category_cache).id

        db.add(models.Product(
            shop_id=shop.id,
            nom=nom,
            reference=str(row.get("reference") or "").strip() or None,
            category_id=category_id,
            prix_achat=max(prix_achat, 0),
            prix_vente=max(prix_vente, 0),
            stock=max(stock, 0),
            seuil_alerte=max(seuil_alerte, 0),
        ))
        crees += 1

    db.commit()
    return {"crees": crees, "erreurs": erreurs}


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_any_module("produits", "commandes", "stock")),
    db: Session = Depends(get_db),
):
    return _get_owned_product(db, shop, product_id)


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    payload: schemas.ProductIn,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, shop, product_id)
    for field, value in payload.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, shop, product_id)
    storage.delete_stored_file(db, product.image_path)
    db.delete(product)
    db.commit()


@router.get("/{product_id}/image")
def get_product_image(product_id: int, db: Session = Depends(get_db)):
    """Public (pas d'authentification) : sert aussi les photos sur la boutique
    publique, consultée sans compte."""
    product = db.get(models.Product, product_id)
    if product is None or not product.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image introuvable")
    stored = storage.get_stored_file(db, product.image_path)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image introuvable")
    return Response(content=stored.data, media_type=stored.content_type)


@router.post("/{product_id}/image", response_model=schemas.ProductOut)
async def upload_product_image(
    product_id: int,
    file: UploadFile,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, shop, product_id)
    try:
        new_path = await storage.save_upload(db, file, "produits", storage.ALLOWED_PHOTO_EXT)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    storage.delete_stored_file(db, product.image_path)
    product.image_path = new_path
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}/image", response_model=schemas.ProductOut)
def remove_product_image(
    product_id: int,
    shop: models.Shop = Depends(get_current_shop),
    _: models.User = Depends(require_module("produits")),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, shop, product_id)
    storage.delete_stored_file(db, product.image_path)
    product.image_path = None
    db.commit()
    db.refresh(product)
    return product
