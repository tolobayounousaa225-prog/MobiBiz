from datetime import date as date_type
from datetime import datetime, timedelta

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..audit import log_admin_action
from ..database import get_db
from ..deps import require_admin, require_super_admin
from ..notifications import notify
from ..plans import PAYMENT_VALIDITY_DAYS, PLAN_FEATURES
from ..receipt_pdf import generate_payment_receipt_pdf
from ..security_utils import csv_safe

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

CANCELLED_STATUSES = {models.OrderStatus.ANNULEE, models.OrderStatus.ECHOUEE}


def _shop_to_admin_out(db: Session, shop: models.Shop) -> schemas.AdminShopOut:
    orders = (
        db.query(models.Order)
        .filter(models.Order.shop_id == shop.id, ~models.Order.statut.in_(CANCELLED_STATUSES))
        .all()
    )
    nombre_produits = db.query(models.Product).filter(models.Product.shop_id == shop.id).count()
    return schemas.AdminShopOut(
        id=shop.id,
        nom=shop.nom,
        slug=shop.slug,
        abonnement_statut=shop.abonnement_statut,
        abonnement_plan=shop.abonnement_plan,
        prochain_paiement_le=shop.prochain_paiement_le.isoformat() if shop.prochain_paiement_le else None,
        essai_expire_le=shop.essai_expire_le.isoformat() if shop.essai_expire_le else None,
        proprietaire_nom=f"{shop.owner.prenom} {shop.owner.nom}",
        proprietaire_telephone=shop.owner.telephone,
        nombre_produits=nombre_produits,
        nombre_commandes=len(orders),
        chiffre_affaires=sum(o.total for o in orders),
        created_at=shop.created_at,
    )


def _get_shop_or_404(db: Session, shop_id: int) -> models.Shop:
    shop = db.get(models.Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boutique introuvable")
    return shop


@router.get("/boutiques", response_model=list[schemas.AdminShopOut])
def list_shops(db: Session = Depends(get_db)):
    shops = db.query(models.Shop).order_by(models.Shop.created_at.desc()).all()
    return [_shop_to_admin_out(db, shop) for shop in shops]


@router.get("/boutiques/{shop_id}", response_model=schemas.AdminShopOut)
def get_shop(shop_id: int, db: Session = Depends(get_db)):
    return _shop_to_admin_out(db, _get_shop_or_404(db, shop_id))


@router.patch("/boutiques/{shop_id}/statut", response_model=schemas.AdminShopOut)
def update_shop_status(
    shop_id: int, payload: schemas.AdminShopStatusIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    shop = _get_shop_or_404(db, shop_id)
    ancien = shop.abonnement_statut.value
    shop.abonnement_statut = payload.abonnement_statut
    log_admin_action(db, admin, "changement_statut", "boutique", shop.id,
                      f"{ancien} -> {payload.abonnement_statut.value} ({shop.nom})")
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


@router.patch("/boutiques/{shop_id}/abonnement", response_model=schemas.AdminShopOut)
def update_shop_plan(
    shop_id: int, payload: schemas.AdminShopPlanIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    shop = _get_shop_or_404(db, shop_id)
    ancien = shop.abonnement_plan.value
    shop.abonnement_plan = payload.abonnement_plan
    log_admin_action(db, admin, "changement_plan", "boutique", shop.id,
                      f"{ancien} -> {payload.abonnement_plan.value} ({shop.nom})")
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


@router.get("/utilisateurs", response_model=list[schemas.AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    result = []
    for user in users:
        boutique_nom = None
        if user.role == models.UserRole.OWNER:
            shop = db.query(models.Shop).filter(models.Shop.owner_id == user.id).first()
            boutique_nom = shop.nom if shop else None
        elif user.role == models.UserRole.EMPLOYEE and user.shop_id:
            shop = db.get(models.Shop, user.shop_id)
            boutique_nom = shop.nom if shop else None
        result.append(schemas.AdminUserOut(
            id=user.id, nom=user.nom, prenom=user.prenom, telephone=user.telephone,
            role=user.role, employee_role=user.employee_role, actif=user.actif,
            boutique_nom=boutique_nom, created_at=user.created_at,
        ))
    return result


@router.get("/statistiques", response_model=schemas.AdminStatsOut)
def get_statistics(db: Session = Depends(get_db)):
    shops = db.query(models.Shop).all()
    orders = db.query(models.Order).filter(~models.Order.statut.in_(CANCELLED_STATUSES)).all()

    return schemas.AdminStatsOut(
        boutiques_total=len(shops),
        boutiques_actives=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.ACTIF),
        boutiques_suspendues=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.SUSPENDU),
        boutiques_essai=sum(1 for s in shops if s.abonnement_statut == models.SubscriptionStatus.ESSAI),
        utilisateurs_total=db.query(models.User).filter(models.User.role != models.UserRole.ADMIN).count(),
        commandes_total=len(orders),
        chiffre_affaires_total=sum(o.total for o in orders),
        parrainages_total=sum(1 for s in shops if s.referred_by_shop_id is not None),
    )


@router.get("/boutiques/{shop_id}/paiements", response_model=list[schemas.SubscriptionPaymentOut])
def list_shop_payments(shop_id: int, db: Session = Depends(get_db)):
    _get_shop_or_404(db, shop_id)
    return (
        db.query(models.SubscriptionPayment)
        .filter(models.SubscriptionPayment.shop_id == shop_id)
        .order_by(models.SubscriptionPayment.date_paiement.desc())
        .all()
    )


@router.get("/boutiques/{shop_id}/paiements/{payment_id}/recu.pdf")
def download_shop_payment_receipt(shop_id: int, payment_id: int, db: Session = Depends(get_db)):
    """Permet à l'admin de récupérer lui-même le PDF pour le transmettre
    manuellement à la boutique (WhatsApp, email...) si besoin — le reçu est de
    toute façon déjà consultable directement par la boutique dans son propre
    espace dès qu'il est généré."""
    payment = (
        db.query(models.SubscriptionPayment)
        .filter(models.SubscriptionPayment.id == payment_id, models.SubscriptionPayment.shop_id == shop_id)
        .first()
    )
    if payment is None or not payment.recu_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reçu introuvable")
    stored = storage.get_stored_file(db, payment.recu_path)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reçu introuvable")
    return Response(
        content=stored.data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recu-{payment.date_paiement}.pdf"'},
    )


@router.post("/boutiques/{shop_id}/paiements", response_model=schemas.AdminShopOut, status_code=status.HTTP_201_CREATED)
def record_shop_payment(
    shop_id: int, payload: schemas.SubscriptionPaymentIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    shop = _get_shop_or_404(db, shop_id)
    try:
        parsed_date = date_type.fromisoformat(payload.date_paiement)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format attendu AAAA-MM-JJ)")

    payment = models.SubscriptionPayment(shop_id=shop.id, montant=payload.montant, date_paiement=parsed_date)
    db.add(payment)
    db.flush()  # nécessaire pour avoir payment.id avant de générer le reçu

    pdf_bytes = generate_payment_receipt_pdf(shop, payment)
    payment.recu_path = storage.save_bytes(db, pdf_bytes, "recus", f"recu-{payment.id}.pdf", "application/pdf")

    shop.prochain_paiement_le = parsed_date + timedelta(days=PAYMENT_VALIDITY_DAYS)
    notify(
        db, shop.id, models.NotificationType.PAIEMENT_RECU,
        f"Paiement d'abonnement de {payload.montant:.0f} FCFA enregistré — reçu disponible dans votre espace.",
    )
    log_admin_action(db, admin, "paiement_enregistre", "boutique", shop.id,
                      f"{payload.montant:.0f} FCFA le {payload.date_paiement} ({shop.nom})")
    db.commit()
    db.refresh(shop)
    return _shop_to_admin_out(db, shop)


def _get_or_create_platform_settings(db: Session) -> models.PlatformSettings:
    settings_row = db.get(models.PlatformSettings, 1)
    if settings_row is None:
        settings_row = models.PlatformSettings(id=1)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


@router.get("/parametres", response_model=schemas.PlatformSettingsOut)
def get_platform_settings(db: Session = Depends(get_db)):
    return _get_or_create_platform_settings(db)


@router.put("/parametres", response_model=schemas.PlatformSettingsOut)
def update_platform_settings(
    payload: schemas.PlatformSettingsIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    settings_row = _get_or_create_platform_settings(db)
    settings_row.wave_payment_link = payload.wave_payment_link
    log_admin_action(db, admin, "parametres_modifies", "plateforme", None, "lien de paiement Wave mis à jour")
    db.commit()
    db.refresh(settings_row)
    return settings_row


@router.get("/journal", response_model=list[schemas.AuditLogOut])
def get_audit_log(limit: int = 100, db: Session = Depends(get_db)):
    entries = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(min(limit, 300))
        .all()
    )
    return [
        schemas.AuditLogOut(
            id=e.id, admin_nom=f"{e.admin.prenom} {e.admin.nom}", action=e.action,
            cible_type=e.cible_type, cible_id=e.cible_id, details=e.details, created_at=e.created_at,
        )
        for e in entries
    ]


@router.get("/administrateurs", response_model=list[schemas.AdminAccountOut])
def list_admins(db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.role == models.UserRole.ADMIN).order_by(models.User.created_at).all()


@router.post("/administrateurs", response_model=schemas.AdminAccountOut, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: schemas.AdminCreateIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    from ..security import hash_password

    existing = db.query(models.User).filter(models.User.telephone == payload.telephone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce numéro est déjà utilisé")

    new_admin = models.User(
        nom=payload.nom, prenom=payload.prenom, telephone=payload.telephone,
        password_hash=hash_password(payload.password), role=models.UserRole.ADMIN,
        admin_role=payload.admin_role,
    )
    db.add(new_admin)
    db.flush()
    log_admin_action(db, admin, "admin_cree", "utilisateur", new_admin.id,
                      f"{payload.prenom} {payload.nom} ({payload.admin_role.value})")
    db.commit()
    db.refresh(new_admin)
    return new_admin


@router.get("/tickets", response_model=list[schemas.TicketOut])
def list_all_tickets(db: Session = Depends(get_db)):
    tickets = db.query(models.SupportTicket).order_by(models.SupportTicket.created_at.desc()).all()
    return [_ticket_to_out(t) for t in tickets]


@router.patch("/tickets/{ticket_id}/statut", response_model=schemas.TicketOut)
def update_ticket_status(
    ticket_id: int, payload: schemas.TicketStatusIn,
    admin: models.User = Depends(require_admin), db: Session = Depends(get_db),
):
    ticket = db.get(models.SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket introuvable")
    ticket.statut = payload.statut
    log_admin_action(db, admin, "ticket_statut", "ticket", ticket.id, payload.statut.value)
    db.commit()
    db.refresh(ticket)
    return _ticket_to_out(ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=schemas.TicketOut, status_code=status.HTTP_201_CREATED)
def admin_reply_ticket(
    ticket_id: int, payload: schemas.TicketMessageIn,
    admin: models.User = Depends(require_admin), db: Session = Depends(get_db),
):
    ticket = db.get(models.SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket introuvable")
    db.add(models.TicketMessage(ticket_id=ticket.id, auteur_id=admin.id, message=payload.message))
    db.commit()
    db.refresh(ticket)
    return _ticket_to_out(ticket)


def _ticket_to_out(ticket: models.SupportTicket) -> schemas.TicketOut:
    return schemas.TicketOut(
        id=ticket.id, sujet=ticket.sujet, statut=ticket.statut,
        boutique_nom=ticket.shop.nom if ticket.shop else None, created_at=ticket.created_at,
        messages=[
            schemas.TicketMessageOut(
                id=m.id, auteur_id=m.auteur_id, auteur_nom=f"{m.auteur.prenom} {m.auteur.nom}",
                auteur_role=m.auteur.role, message=m.message, created_at=m.created_at,
            )
            for m in ticket.messages
        ],
    )


@router.get("/statistiques/evolution", response_model=list[schemas.MonthlyStatOut])
def get_evolution_statistics(mois: int = 6, db: Session = Depends(get_db)):
    from datetime import date, datetime

    today = date.today()
    results = []
    for i in range(mois - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        start_date = date(year, month, 1)
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        # Bornes datetime *naïves* (pas de tzinfo) : SQLite stocke created_at sans
        # fuseau (voir ensure_aware dans models.py) et sérialise un datetime "aware"
        # avec un suffixe +00:00 qui casse la comparaison lexicographique SQLite —
        # rester naïf ici fonctionne correctement sur SQLite ET Postgres, puisque
        # now_utc() n'écrit jamais que de l'UTC des deux côtés.
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.min.time())

        nouvelles_boutiques = (
            db.query(models.Shop)
            .filter(models.Shop.created_at >= start, models.Shop.created_at < end)
            .count()
        )
        orders = (
            db.query(models.Order)
            .filter(
                models.Order.created_at >= start, models.Order.created_at < end,
                ~models.Order.statut.in_(CANCELLED_STATUSES),
            )
            .all()
        )
        results.append(schemas.MonthlyStatOut(
            mois=start.strftime("%Y-%m"),
            nouvelles_boutiques=nouvelles_boutiques,
            commandes=len(orders),
            chiffre_affaires=sum(o.total for o in orders),
        ))
    return results


@router.get("/notifications", response_model=schemas.AdminNotificationsOut)
def get_admin_notifications(db: Session = Depends(get_db)):
    today = date_type.today()
    tickets_ouverts = db.query(models.SupportTicket).filter(models.SupportTicket.statut == models.TicketStatus.OUVERT).count()
    paiements_en_retard = (
        db.query(models.Shop)
        .filter(
            models.Shop.abonnement_statut == models.SubscriptionStatus.ACTIF,
            models.Shop.prochain_paiement_le.isnot(None),
            models.Shop.prochain_paiement_le < today,
        )
        .count()
    )
    nouvelles_boutiques_7j = (
        db.query(models.Shop)
        .filter(models.Shop.created_at >= datetime.combine(today - timedelta(days=7), datetime.min.time()))
        .count()
    )
    essais_expirant_bientot = (
        db.query(models.Shop)
        .filter(
            models.Shop.abonnement_statut == models.SubscriptionStatus.ESSAI,
            models.Shop.essai_expire_le.isnot(None),
            models.Shop.essai_expire_le >= today,
            models.Shop.essai_expire_le <= today + timedelta(days=3),
        )
        .count()
    )
    return schemas.AdminNotificationsOut(
        tickets_ouverts=tickets_ouverts,
        paiements_en_retard=paiements_en_retard,
        nouvelles_boutiques_7j=nouvelles_boutiques_7j,
        essais_expirant_bientot=essais_expirant_bientot,
    )


@router.get("/statistiques/revenus", response_model=schemas.PlatformRevenueOut)
def get_platform_revenue(db: Session = Depends(get_db)):
    shops_actives = db.query(models.Shop).filter(models.Shop.abonnement_statut == models.SubscriptionStatus.ACTIF).all()
    mrr_estime = sum((PLAN_FEATURES.get(s.abonnement_plan, {}).get("prix_mensuel") or 0) for s in shops_actives)

    total_encaisse = db.query(func.sum(models.SubscriptionPayment.montant)).scalar() or 0
    debut_mois = date_type.today().replace(day=1)
    encaisse_mois_courant = (
        db.query(func.sum(models.SubscriptionPayment.montant))
        .filter(models.SubscriptionPayment.date_paiement >= debut_mois)
        .scalar() or 0
    )

    repartition_counts: dict[models.SubscriptionPlan, int] = {}
    for s in shops_actives:
        repartition_counts[s.abonnement_plan] = repartition_counts.get(s.abonnement_plan, 0) + 1

    return schemas.PlatformRevenueOut(
        mrr_estime=mrr_estime,
        total_encaisse=total_encaisse,
        encaisse_mois_courant=encaisse_mois_courant,
        repartition_plans=[schemas.PlanRepartitionOut(plan=p, nombre=n) for p, n in repartition_counts.items()],
    )


@router.post("/boutiques/{shop_id}/impersonate", response_model=schemas.ImpersonateOut)
def impersonate_shop(
    shop_id: int,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    """Génère un token d'accès pour le propriétaire de la boutique, afin que
    l'admin puisse diagnostiquer un problème signalé sans connaître son mot de
    passe. Action tracée dans le journal d'audit — c'est ce qui en fait le seul
    contrôle en place (pas de restriction technique sur ce que l'admin peut voir
    une fois "connecté" à la place du propriétaire)."""
    from ..security import create_access_token

    shop = _get_shop_or_404(db, shop_id)
    token = create_access_token(str(shop.owner_id))
    log_admin_action(db, admin, "connexion_en_tant_que", "boutique", shop.id,
                      f"{shop.nom} (propriétaire #{shop.owner_id})")
    db.commit()
    return schemas.ImpersonateOut(access_token=token, boutique_nom=shop.nom)


@router.post("/boutiques/actions-groupees", response_model=schemas.AdminBulkActionOut)
def bulk_update_shop_status(
    payload: schemas.AdminBulkStatusIn,
    admin: models.User = Depends(require_super_admin), db: Session = Depends(get_db),
):
    shops = db.query(models.Shop).filter(models.Shop.id.in_(payload.shop_ids)).all()
    for shop in shops:
        shop.abonnement_statut = payload.abonnement_statut
    log_admin_action(
        db, admin, "changement_statut_groupe", "boutique", None,
        f"{len(shops)} boutique(s) -> {payload.abonnement_statut.value} ({', '.join(s.nom for s in shops)})",
    )
    db.commit()
    return schemas.AdminBulkActionOut(mis_a_jour=len(shops), boutiques=[s.nom for s in shops])


@router.get("/export/boutiques.csv")
def export_shops_csv(db: Session = Depends(get_db)):
    shops = db.query(models.Shop).order_by(models.Shop.created_at.desc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "ID", "Boutique", "Propriétaire", "Téléphone", "Plan", "Statut",
        "Essai expire le", "Prochain paiement le", "Inscrite le",
    ])
    for s in shops:
        writer.writerow([
            s.id, csv_safe(s.nom), csv_safe(f"{s.owner.prenom} {s.owner.nom}"), csv_safe(s.owner.telephone),
            s.abonnement_plan.value, s.abonnement_statut.value,
            s.essai_expire_le.isoformat() if s.essai_expire_le else "",
            s.prochain_paiement_le.isoformat() if s.prochain_paiement_le else "",
            s.created_at.date().isoformat(),
        ])
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="boutiques.csv"'},
    )


@router.get("/export/paiements.csv")
def export_payments_csv(db: Session = Depends(get_db)):
    payments = (
        db.query(models.SubscriptionPayment)
        .order_by(models.SubscriptionPayment.date_paiement.desc())
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Boutique", "Montant (FCFA)", "Date de paiement", "Enregistré le"])
    for p in payments:
        writer.writerow([
            csv_safe(p.shop.nom) if p.shop else "", p.montant,
            p.date_paiement.isoformat(), p.created_at.date().isoformat(),
        ])
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="paiements.csv"'},
    )
