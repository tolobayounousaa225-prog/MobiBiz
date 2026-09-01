# MobiBiz

> Vendez. Gérez. Développez.

Plateforme de gestion commerciale pour les commerçants qui vendent via WhatsApp et les
réseaux sociaux en Côte d'Ivoire. Voir le cahier des charges complet fourni par
l'utilisateur pour la vision produit complète (40 sections, modules 1 à 15).

## État actuel : MVP (V1 — section 29 du cahier des charges)

Implémenté et testé de bout en bout :
- Authentification (inscription commerçant + création automatique de sa boutique, connexion, JWT)
- Boutique (informations de la boutique)
- Produits (catalogue, catégories, recherche, filtre stock faible)
- Clients (fiche client, segmentation automatique nouveau / régulier / VIP / inactif)
- Commandes (création multi-produits, machine à états, décrément automatique du stock,
  restockage automatique en cas d'annulation/retour/échec)
- Stock (ajustement manuel, historique des mouvements, alertes de seuil)
- Tableau de bord (CA, commandes, clients, produits, bénéfice estimé, impayés)
- Rapports simples (export CSV ventes / produits / clients, protégé contre l'injection
  de formule CSV)

**Non implémenté volontairement** (prévu aux versions suivantes du cahier des charges,
section 30 et suivantes) : paiements en ligne, notifications, employés/rôles, dépenses,
import Excel, boutique publique (V2) ; livraison, intégrations WhatsApp, marketing,
fidélisation (V3) ; assistant IA (V4) ; marketplace multi-acteurs (V5).

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
