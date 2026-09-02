# MobiBiz

> Vendez. Gérez. Développez.

Plateforme de gestion commerciale pour les commerçants qui vendent via WhatsApp et les
réseaux sociaux en Côte d'Ivoire. Voir le cahier des charges complet fourni par
l'utilisateur pour la vision produit complète (40 sections, modules 1 à 15).

## État actuel : MVP (V1 — section 29 du cahier des charges)

Implémenté et testé de bout en bout :
- Authentification (inscription commerçant + création automatique de sa boutique, connexion, JWT,
  réinitialisation du mot de passe par question de sécurité — voir plus bas)
- Boutique (informations de la boutique)
- Produits (catalogue, catégories, recherche, filtre stock faible)
- Clients (fiche client, segmentation automatique nouveau / régulier / VIP / inactif)
- Commandes (création multi-produits, machine à états, décrément automatique du stock,
  restockage automatique en cas d'annulation/retour/échec)
- Stock (ajustement manuel, historique des mouvements, alertes de seuil)
- Tableau de bord (CA, commandes, clients, produits, bénéfice estimé, impayés)
- Rapports simples (export CSV ventes / produits / clients, protégé contre l'injection
  de formule CSV)

## V2

- **Paiement Wave (QR code)** ✅ — le commerçant enregistre son lien de paiement Wave
  Business (page « Ma boutique »), un QR code est généré côté serveur et affichable
  depuis la boutique et depuis chaque commande (avec le montant à encaisser). Pas
  d'API paiement (Wave n'en expose pas à un petit marchand) : confirmation du paiement
  reçu toujours manuelle.
- **Employés & rôles** ✅ — le propriétaire crée des comptes vendeur / magasinier /
  comptable / manager (page « Employés »), chacun avec un accès restreint par module
  (produits, commandes, stock, finance) appliqué côté backend (`deps.require_module`)
  et reflété côté frontend (menu filtré par rôle dans `layout.js`).
- **Notifications in-app** ✅ — cloche avec compteur non lu (nouvelle commande, stock
  faible, paiement reçu). Pas de SMS/WhatsApp/push navigateur : nécessiterait un
  service tiers (Twilio, VAPID...) non configuré pour l'instant.
- **Finances & dépenses** ✅ — page « Finances » (dépenses par catégorie + résumé CA /
  coût produits / dépenses / bénéfice réel), réservée au propriétaire et au comptable.
- **Import CSV/Excel de produits** ✅ — modèle téléchargeable, rapport d'erreurs ligne
  par ligne, catégories créées à la volée si absentes.
- **Boutique publique** ✅ — page client sans compte (`boutique-publique.html?slug=...`),
  activable depuis les paramètres boutique, catalogue + commande invité.

## V3

- **Livraison** ✅ — mode (interne / livreur partenaire / retrait boutique), livreur,
  adresse et commune de livraison (indépendantes de celles du client), heure prévue,
  note de preuve, gérés depuis la fiche commande.
- **WhatsApp** ✅ — pas d'API WhatsApp Business (nécessiterait un compte Meta Business +
  un fournisseur agréé que l'utilisateur n'a pas encore) : liens `wa.me` pré-remplis à la
  place (confirmation/livraison/livrée depuis une commande, bouton flottant sur la
  boutique publique, campagnes par segment). `assets/js/api.js` expose `waLink(phone,
  message)` et `toWhatsAppNumber(phone)` (normalise 07/05/01... vers le format
  international attendu par wa.me) pour toute future page qui en aurait besoin.
- **Promotions** ✅ — `prix_promo` + `promo_actif` sur chaque produit, appliqués via
  `Product.effective_price` aussi bien pour les commandes internes que pour la boutique
  publique (un seul point de calcul du prix facturé, pour éviter que les deux chemins
  divergent).
- **Marketing / fidélisation** ✅ — page dédiée : compteurs par segment client, message
  personnalisable (`{nom}`), un lien WhatsApp généré par client ciblé — pas d'envoi
  groupé automatique, faute d'API d'envoi en masse.
- **Photo produit (optionnelle)** ✅ — une photo par produit, stockée en base de données
  (`stored_files`, `app/storage.py`) et non sur disque : Railway ne fournit pas de disque
  persistant à `mobibiz-backend` (même contrainte que LECIM), tout fichier écrit sur le
  disque du conteneur disparaîtrait au prochain déploiement. Servie via
  `GET /api/produits/{id}/image` (public, nécessaire pour la boutique publique). Upload
  validé par whitelist d'extension + vérification des magic bytes, 5 Mo max
  (`settings.max_upload_size_mb`).
- **Réinitialisation du mot de passe (par question de sécurité)** ✅ — aucun service
  SMS/email configuré pour un code ou un lien de reset classique : chaque compte
  définit une question de sécurité (liste prédéfinie, `schemas.SECURITY_QUESTIONS`) à
  l'inscription ; en cas d'oubli, `mot-de-passe-oublie.html` demande le numéro, affiche
  la question, et permet de choisir un nouveau mot de passe si la réponse correspond
  (insensible à la casse/espaces). Rate-limité par IP et par numéro ciblé (réponse à
  faible entropie). Page `mon-compte.html` ajoutée pour changer son mot de passe une
  fois connecté et définir/modifier sa question de sécurité — nécessaire pour les
  comptes créés avant cette fonctionnalité et pour les employés (créés par le
  propriétaire, qui ne peut pas répondre à leur place).

- **Administration plateforme** ✅ — Module 15 du cahier des charges. Rôle `admin`
  (existait déjà dans `UserRole` depuis le V1, jamais exploité) : espace séparé
  (`admin-dashboard.html`, `admin-boutiques.html`, `admin-utilisateurs.html`,
  `assets/js/admin-layout.js`) pour superviser toutes les boutiques inscrites — statut
  d'abonnement (essai/actif/suspendu) et plan (free/starter/pro/business/enterprise) par
  boutique. Suspendre une boutique bloque tout accès (back-office **et** boutique
  publique) via `deps.get_current_shop` (402) — un seul point de contrôle plutôt que de
  modifier chaque router. **Aucune auto-inscription admin** : le compte s'ajoute
  uniquement en base directement (`railway ssh`), jamais via l'API publique.
- **Paiement d'abonnement (QR Wave)** ✅ — boucle la suspension : lien Wave niveau
  plateforme configurable dans `admin-parametres.html` (`PlatformSettings`, ligne
  unique), QR servi via `GET /api/abonnement/wave-qr.png` (accessible à tout compte
  connecté, pas seulement l'admin — visible depuis `boutique.html`). Chaque paiement
  reçu, enregistré manuellement par l'admin (`SubscriptionPayment`), recalcule
  `shops.prochain_paiement_le` (+30 jours). Dashboard admin : section « échéances
  proches » (badge rouge en retard, orange ≤5 jours) — pas d'auto-suspension à
  l'échéance pour l'instant, décision manuelle de l'admin.
- **Journal d'audit** ✅ — `AuditLog` trace chaque action admin (suspension, plan,
  paiement, paramètres, création d'admin, statut de ticket) avec qui/quand/quoi.
  Consultable sur `admin-journal.html`.
- **Essai gratuit auto-expirable** ✅ — nouvelle boutique = 14 jours d'essai
  (`plans.TRIAL_DAYS`), `essai_expire_le` fixé à l'inscription. Vérification
  paresseuse dans `deps.get_current_shop` (pas de tâche planifiée) : au premier accès
  après l'échéance, bascule automatiquement en suspendu et se persiste.
- **Support / tickets** ✅ — `support.html` (boutique) / `admin-tickets.html` (admin),
  statut ouvert/résolu, fil de messages.
- **Plans avec avantages et souscription** ✅ — `app/plans.py` centralise prix et
  limites par plan (produits/employés/boutique publique), exposé via
  `GET /api/abonnement/plans` et affiché sur `plans.html`. Limites appliquées côté
  serveur. Souscription en libre-service (immédiate, sans validation admin) — le
  paiement reste suivi séparément (QR Wave), un plan choisi mais non payé finit par
  apparaître en retard dans le dashboard admin.
- **Comptes admin depuis l'interface** ✅ — `POST /api/admin/administrateurs`,
  réservé aux admins existants (toujours aucune auto-inscription publique).
- **Statistiques d'évolution** ✅ — nouvelles boutiques/commandes/CA par mois
  (`GET /api/admin/statistiques/evolution`), graphique en barres SVG fait main sur
  `admin-dashboard.html` (pas de dépendance externe).
- **Statistiques stock avancées** ✅ — section 14 du cahier des charges.
  `GET /api/stock/statistiques` (`jours_ventes`=30, `jours_dormant`=60, `limite`=10,
  tous ajustables en query param) : valeur du stock au prix d'achat et de vente,
  bénéfice potentiel, rotation globale (qté vendue / stock actuel sur la fenêtre de
  vente — approximation faute d'historique de stock moyen), produits les plus/moins
  vendus (avec au moins une vente), stock dormant (aucune vente sur la fenêtre
  `jours_dormant`, trié par valeur immobilisée décroissante pour prioriser). Affiché
  en haut de `stock.html` (KPI + 3 tableaux), bouton « Ajuster » direct depuis le
  tableau de stock dormant.

## Boutique et administration — 2e vague (2026-09-02)

Côté boutique :
- **Variantes produits** ✅ — `ProductVariant` (taille/couleur/modèle), chacune avec
  son propre stock et prix. `Product.has_variants` bascule la vente : produit
  simple → `product.stock`/`prix_vente` ; produit à variantes → la commande DOIT
  préciser `variant_id`, stock décrémenté sur la variante (interne, boutique
  publique, annulation/retour). Géré depuis `produits.html` (section dépliable dans
  la fiche produit, activable seulement une fois le produit enregistré).
- **Codes promo / coupons** ✅ — `Coupon` (pourcentage ou montant fixe, dates de
  validité, usage max), distinct de la remise automatique `prix_promo`. Validation
  et calcul centralisés dans `routers/coupons.py::validate_and_apply_coupon`,
  appelé à la fois par la commande interne et la commande boutique publique (pour
  ne pas reproduire le bug déjà rencontré avec `effective_price` dupliqué). Gestion
  CRUD sur `coupons.html` (propriétaire uniquement).
- **Factures PDF** ✅ — `GET /api/commandes/{id}/facture.pdf`, généré avec
  `reportlab` (pur Python, pas de dépendance système type pango/cairo — s'installe
  sans souci sur l'image Docker Railway). Bouton de téléchargement sur le détail
  d'une commande dans `commandes.html`.
- **Avis clients** ✅ — `ProductReview`, soumis sans compte depuis la boutique
  publique (modéré : `approuve=False` par défaut, visible publiquement seulement
  après validation du commerçant depuis `produits.html`). Rate-limité par IP.
  Moyenne/nombre affichés sur la fiche produit publique.

Côté administration plateforme :
- **Notifications admin** ✅ — `GET /api/admin/notifications` (calculé à la volée,
  pas de table dédiée) : tickets ouverts, paiements en retard, essais expirant
  sous 3 jours, nouvelles boutiques (7j). Cloche dans `admin-layout.js`, même
  pattern que la cloche boutique.
- **Revenus plateforme** ✅ — `GET /api/admin/statistiques/revenus` : MRR estimé
  (somme des prix des plans des boutiques actives), encaissé ce mois-ci et total
  historique (`SubscriptionPayment`), répartition par plan. Section dédiée sur
  `admin-dashboard.html`.
- **Connexion en tant que** ✅ — `POST /api/admin/boutiques/{id}/impersonate`
  (SUPER uniquement) génère un token pour le propriétaire de la boutique, pour
  diagnostiquer un problème signalé sans connaître son mot de passe. Tracé dans le
  journal d'audit (seul garde-fou — pas de restriction technique sur ce que l'admin
  peut voir une fois "connecté"). Le frontend garde le token admin de côté
  (`Auth.startImpersonation`) et affiche un bandeau « Quitter » sur tout l'espace
  boutique (`layout.js`) pour revenir sans se reconnecter.
- **Rôles admin (SUPER / SUPPORT)** ✅ — `User.admin_role`, nouvelle dépendance
  `require_super_admin` en plus de `require_admin`. SUPPORT : accès tickets et
  consultation seule (boutiques, utilisateurs, journal, statistiques) ; SUPER :
  accès complet (suspension, plans, paiements, paramètres, création d'admin,
  connexion en tant que). Comptes admin déjà existants migrés en SUPER
  automatiquement (`_backfill_admin_roles`) pour ne rien changer à leur
  comportement actuel. Nav admin et boutons sensibles masqués côté frontend selon
  le rôle, en plus du contrôle serveur (le frontend ne fait qu'améliorer l'UX, le
  403 serveur reste l'unique garde-fou réel).

## Boutique et administration — 3e vague (2026-09-02)

Côté boutique :
- **Galerie multi-photos** ✅ — `ProductImage` (nouvelle table), jusqu'à 8 photos
  supplémentaires par produit en plus de la photo principale (`Product.image_path`,
  inchangée). Gérée depuis `produits.html`, affichée en vignettes cliquables sur la
  fiche produit de la boutique publique (`boutique-publique.html`).
- **Rapports PDF** ✅ — `GET /api/rapports/ventes.pdf` et `/finances.pdf`
  (`app/reports_pdf.py`, reportlab). Complète les exports CSV existants sans les
  remplacer : KPIs, top produits vendus, détail des commandes/dépenses.
- **Étiquettes QR produit** ✅ — `GET /api/produits/{id}/etiquette.pdf?quantite=N`
  (`app/labels.py`) : planche d'étiquettes (QR + nom + prix) à imprimer, jusqu'à 60
  par génération. QR plutôt qu'un vrai code-barres EAN13 (nécessiterait un
  identifiant GS1 attribué, hors de portée) — lisible par n'importe quel scanner QR,
  y compris un smartphone.

Côté administration plateforme :
- **Actions groupées** ✅ — `POST /api/admin/boutiques/actions-groupees` (SUPER
  uniquement), suspend/réactive plusieurs boutiques en un appel. Sélection par
  cases à cocher sur `admin-boutiques.html`, une seule entrée de journal d'audit
  résumant le lot plutôt qu'une par boutique.
- **Export comptable** ✅ — `GET /api/admin/export/boutiques.csv` et
  `/paiements.csv`, protégés par `csv_safe` (même garde anti-injection de formule
  que les autres exports CSV du projet).
- **Bannière d'alerte boutique** ✅ — purement frontend (`layout.js`,
  `renderAccountAlert`), aucune route dédiée : lit `essai_expire_le`/
  `prochain_paiement_le`/`abonnement_statut` déjà renvoyés par `GET /api/boutique`.
  Avertit le commerçant lui-même (essai ≤ 3 jours restants, ou paiement en retard),
  en complément — pas en remplacement — des notifications déjà côté admin.
- **Codes de parrainage** ✅ — `Shop.referral_code` (généré à l'inscription) +
  `Shop.referred_by_shop_id`. Un code valide saisi à l'inscription
  (`inscription.html`, pré-rempli via `?parrain=CODE` dans le lien partagé) prolonge
  de 7 jours (`plans.REFERRAL_BONUS_DAYS`) l'essai/l'échéance de paiement **des deux
  boutiques** — parrain et filleul. Un code invalide n'empêche pas l'inscription,
  juste pas de bonus. Carte dédiée sur `boutique.html` (code + lien à partager +
  nombre de parrainages), compteur `parrainages_total` sur `admin-dashboard.html`.

**Piège rencontré et corrigé avant déploiement** : `reportlab.platypus.Image`
n'accepte pas un `ImageReader` directement en premier argument (malgré ce qu'on
pourrait attendre) — lève `TypeError: expected str, bytes or os.PathLike object`.
Corrigé en passant un `io.BytesIO` frais des bytes PNG à chaque étiquette
(`app/labels.py`) : réutiliser la même instance de flowable (Image/Table/Paragraph)
à plusieurs endroits d'un même document reportlab est de toute façon à éviter, l'état
de mise en page est partagé et le rendu peut devenir incorrect silencieusement.

## Badges d'actions en attente + correctif "Mon compte" admin (2026-09-02)

- **Badges d'actions en attente** ✅ — demande directe de l'utilisateur : il fallait
  voir en un coup d'œil, sans ouvrir chaque section, qu'il y a une commande à
  confirmer, un stock faible ou un avis à modérer. `GET /api/boutique/actions-en-attente`
  (`schemas.PendingActionsOut` : commandes nouvelles, produits en alerte stock,
  avis non modérés) — un seul appel, le frontend décide seul quel badge afficher
  selon les modules réellement accessibles à l'utilisateur (`NAV_ITEMS[].badgeKey`
  dans `layout.js`). Pastille orange directement sur l'onglet concerné de la barre
  latérale (Produits/Stock/Commandes), rafraîchie toutes les 30s comme la cloche de
  notifications.
- **Bug corrigé — "Mon compte" inaccessible côté admin** ✅ — `mon-compte.html`
  appelait `renderLayout()` (script boutique) en dur, qui redirige tout compte
  `role === "admin"` vers `admin-dashboard.html` : la page apparaissait puis
  disparaissait aussitôt pour un administrateur, rendant "Mon compte" totalement
  inaccessible depuis l'espace admin (signalé par l'utilisateur). Corrigé en
  interrogeant `/api/auth/me` d'abord, puis en appelant `renderLayout()` ou
  `renderAdminLayout()` selon le rôle réel — la page est partagée entre les deux
  espaces (mêmes endpoints `/api/auth/*`), il n'y avait pas besoin de la dupliquer.

## Reçus de paiement + logo boutique (2026-09-02)

- **Reçu de paiement d'abonnement traçable** ✅ — demande directe : à chaque
  paiement enregistré par l'admin (`POST /api/admin/boutiques/{id}/paiements`),
  un reçu PDF est généré immédiatement (`app/receipt_pdf.py`, émis au nom de
  MobiBiz — la boutique est ici le payeur, pas l'émetteur) et rangé en base
  (`SubscriptionPayment.recu_path`, `storage.save_bytes` — nouvelle variante de
  `save_upload` pour les fichiers générés côté serveur plutôt qu'uploadés).
  Consultable par la boutique elle-même via `GET /api/boutique/paiements` +
  `GET /api/boutique/paiements/{id}/recu.pdf` (nouveau, scoping par
  `get_current_shop` — une boutique ne peut pas deviner l'id d'un reçu d'une
  autre), affiché dans une nouvelle section « Historique des paiements » sur
  `boutique.html`. Déclenche aussi une notification in-app (réutilise
  `NotificationType.PAIEMENT_RECU`) — traçabilité même si l'admin oublie de
  prévenir de vive voix, objectif explicite de la demande.
- **Logo boutique** ✅ — `Shop.logo_url` (colonne V1) n'avait en réalité jamais
  été exploité : le frontend l'envoyait toujours à `null`. Ajouté `Shop.logo_path`
  (stockage interne, StoredFile, même mécanisme que `Product.image_path`) et
  `Shop.logo_display_url` (calculé) plutôt que de réutiliser telle quelle la
  colonne existante — un attribut ORM mappé ne peut pas aussi porter une
  `@property` du même nom. Upload/suppression depuis `boutique.html`
  (`POST`/`DELETE /api/boutique/logo`), servi publiquement via
  `GET /api/boutique/{id}/logo` (même logique que la photo produit). Affiché sur
  la boutique publique (`boutique-publique.html`) et sur les documents PDF
  téléchargeables — facture, rapport de ventes, rapport financier
  (`app/pdf_utils.py::shop_header_elements`, partagé par `invoice.py` et
  `reports_pdf.py` pour ne pas dupliquer la mise en page en-tête trois fois).
  **Non couvert volontairement** : les étiquettes QR produit (`labels.py`,
  planches 58×30mm — un logo y prendrait trop de place) et le reçu de paiement
  d'abonnement (émis par MobiBiz, pas par la boutique, donc pas sa marque).

`app/migrations.py` (migrations idempotentes au démarrage, même mécanisme que LECIM)
reste le seul moyen sûr de faire évoluer le schéma d'une table déjà créée en
production ; `Base.metadata.create_all()` seul ne suffit pas, tout futur ajout de
colonne doit y passer.

**Non implémenté volontairement** : vraie API WhatsApp Business (nécessite un compte
Meta Business créé par l'utilisateur), paiement mobile money automatisé au-delà du QR
Wave manuel. **Prévu en V4** : assistant IA (nécessite une clé API d'un modèle de
langage, pas encore fournie). **Prévu en V5** : marketplace multi-acteurs.

## Stack technique

- Backend : FastAPI + SQLAlchemy 2, Python
- Base de données : SQLite en local (`backend/mobibiz_dev.db`, généré automatiquement),
  PostgreSQL en production via `DATABASE_URL`
- Frontend : HTML / CSS / JS vanilla (pas de framework), appels REST vers l'API
- Auth : JWT (python-jose) + bcrypt

Stack volontairement alignée sur le projet LECIM (même écosystème que le reste des
projets de l'utilisateur) plutôt que sur la stack NestJS/Next.js/Flutter suggérée par le
cahier des charges.

### Pourquoi SQLite en local

`psycopg2-binary` n'a pas encore de wheel précompilé pour Python 3.14 (celui installé
sur cette machine) et se compile difficilement sans `pg_config`. Comme le dev local n'a
de toute façon pas besoin de Postgres, `requirements.txt` ne l'installe pas : le backend
tourne par défaut en SQLite (`DATABASE_URL` vide) et n'importe jamais `psycopg2`.
`psycopg2-binary` n'est ajouté que dans `requirements-prod.txt`, à installer uniquement
sur l'environnement de déploiement.

## Lancer le projet en local

```bash
cd backend
py -3 -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8010
```

Dans un autre terminal :

```bash
cd frontend
python -m http.server 5510
```

Puis ouvrir `http://127.0.0.1:5510/inscription.html`.

Ou via les configurations `.claude/launch.json` (`backend` / `frontend`) avec l'outil de
prévisualisation.

## Déploiement

- **Dépôt** : https://github.com/tolobayounousaa225-prog/MobiBiz
- **Backend** : déployé sur Railway (projet `marvelous-rejoicing`, service
  `mobibiz-backend`) → https://mobibiz-backend-production.up.railway.app — auto-déploiement
  à chaque push sur `main` (build Docker depuis le `Dockerfile` à la racine du repo).
- **Base de données** : PostgreSQL managé par Railway (service `Postgres` dans le même
  projet), lié au backend via la variable `DATABASE_URL=${{Postgres.DATABASE_URL}}`
  (réseau privé Railway, pas d'exposition publique).
- **Frontend** : déployé sur GitHub Pages → https://tolobayounousaa225-prog.github.io/MobiBiz/
  — auto-déploiement à chaque push sur `main` qui touche `frontend/**`, via le workflow
  `.github/workflows/deploy-frontend.yml` (GitHub Actions, source Pages = « GitHub Actions »
  dans les paramètres du repo). `assets/js/api.js` bascule automatiquement vers l'URL
  Railway de production dès que l'origine n'est pas `localhost`.

Pour redéployer manuellement le backend depuis la racine du repo :
`railway up --service mobibiz-backend`. Logs : `railway logs --service mobibiz-backend`.
Pour redéclencher le déploiement du frontend sans changement de code : onglet Actions du
repo GitHub → workflow « Déployer le frontend sur GitHub Pages » → Run workflow.

## Développement local vs production

Le développement local (`py -3 -m venv venv` + `uvicorn --reload` + `http.server`,
voir plus haut) reste utile pour modifier le code, mais n'est plus nécessaire pour
utiliser l'application au quotidien : le site sur GitHub Pages parle déjà à l'API de
production sur Railway. Les serveurs locaux peuvent être arrêtés entre deux sessions
de développement.

## Prochaines étapes suggérées

1. Test terrain du MVP (section 37, phase 3 du cahier des charges) avant d'ajouter de
   nouvelles fonctionnalités.
2. V2 : paiements (mobile money), notifications, employés/rôles, dépenses/bénéfices,
   import Excel, boutique publique consultable par les clients.
