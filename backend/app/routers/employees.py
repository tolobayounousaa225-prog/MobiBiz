from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_shop, require_owner
from ..security import hash_password

router = APIRouter(prefix="/api/employes", tags=["employes"], dependencies=[Depends(require_owner)])


def _get_shop_employee(db: Session, shop: models.Shop, employee_id: int) -> models.User:
    employee = (
        db.query(models.User)
        .filter(
            models.User.id == employee_id,
            models.User.shop_id == shop.id,
            models.User.role == models.UserRole.EMPLOYEE,
        )
        .first()
    )
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employé introuvable")
    return employee


@router.get("", response_model=list[schemas.EmployeeOut])
def list_employees(shop: models.Shop = Depends(get_current_shop), db: Session = Depends(get_db)):
    return (
        db.query(models.User)
        .filter(models.User.shop_id == shop.id, models.User.role == models.UserRole.EMPLOYEE)
        .order_by(models.User.created_at)
        .all()
    )


@router.post("", response_model=schemas.EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: schemas.EmployeeIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    existing = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce numéro est déjà utilisé")

    employee = models.User(
        nom=payload.nom,
        prenom=payload.prenom,
        telephone=payload.telephone,
        password_hash=hash_password(payload.password),
        role=models.UserRole.EMPLOYEE,
        shop_id=shop.id,
        employee_role=payload.employee_role,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.put("/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(
    employee_id: int,
    payload: schemas.EmployeeUpdateIn,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    employee = _get_shop_employee(db, shop, employee_id)
    employee.employee_role = payload.employee_role
    employee.actif = payload.actif
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_employee(
    employee_id: int,
    shop: models.Shop = Depends(get_current_shop),
    db: Session = Depends(get_db),
):
    employee = _get_shop_employee(db, shop, employee_id)
    employee.actif = False
    db.commit()
