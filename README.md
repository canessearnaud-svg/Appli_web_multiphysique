# Appli web multiphysique

Application web de simulation multiphysique (mécanique / schéma cinématique, hydraulique,
pneumatique, électrotechnique, automatisme) avec jumeaux numériques de systèmes réels.

Un seul produit, deux déploiements possibles :

- **cloud** : accessible de partout (étudiants, simulations « offline ») ;
- **local atelier** : même pile Docker sur le réseau local uniquement, connectée aux machines
  réelles (OPC UA / Modbus) pour les jumeaux temps réel et la supervision (IHM/SCADA).
  L'instance locale ne doit jamais être exposée publiquement.

## Démarrage rapide (Docker)

```bash
docker compose up --build
```

- Frontend : http://localhost:5173
- API : http://localhost:8000 (doc interactive : http://localhost:8000/docs)

Connexion de développement : indiquer un e-mail (un jeton de session est créé).
À remplacer plus tard par une vraie authentification (OAuth2 / Keycloak).

## Développement hors Docker

Backend :

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload        # API sur :8000
python -m app.worker                  # worker de simulation (nécessite Redis + PostgreSQL)
python -m pytest tests -q             # tests
```

Frontend :

```bash
cd frontend
npm install
npm run dev                           # sur :5173, proxy /api et /ws vers localhost:8000
```

## Architecture

```
Navigateur ──HTTPS──► frontend (React/TS, Vite)
                          │ REST + WebSocket
                          ▼
                    API (FastAPI) ──► file de jobs (Redis / RQ)
                          │                  │
                          ▼                  ▼
                    PostgreSQL        workers de simulation
                  (users, projects,   (solveur acausal DAE,
                   diagrams, runs)     multibody cinématique,
                                        automate IEC 61131-3, FMI)
                          │
                          ▼ WebSocket /ws/runs/{id}
                    résultats temps réel dans le navigateur
```

Chaque simulation est un job isolé (un processus worker par run, quotas à venir), et chaque
ligne de la base porte un `owner_id` filtré systématiquement : le multi-utilisateur repose là-dessus.

## Structure

```
├── docker-compose.yml      # db + redis + backend + worker + frontend
├── backend/
│   ├── app/
│   │   ├── main.py         # API REST + WebSocket
│   │   ├── auth.py         # login dev + dépendance d'authentification (jeton)
│   │   ├── models.py       # users, sessions, projects, diagrams, runs
│   │   ├── queue.py        # file RQ "sim"
│   │   ├── worker.py       # processus worker
│   │   └── sim/
│   │       ├── engine.py   # dispatch des runs
│   │       └── mechanics/kinematics.py   # solveur cinématique planaire (corps + liaisons)
│   └── tests/test_kinematics.py
└── frontend/               # React + TypeScript + Vite
```

## Feuille de route

1. Éditeur web de schéma cinématique 2D — v1 faite : canvas (solides, bâti, liaisons pivot / glissière / encastrement, moteur), sauvegarde par projet, analyse structurelle (mobilité m, hyperstatisme h, formule de Grübler planaire), simulation animée (solveur Newton–Raphson + Levenberg–Marquardt en repli). Reste : symboles ISO 3952 complets, graphe des liaisons, vue 3D
2. Hydraulique 0D + solveur raide + vérin couplé mécanique ↔ fluide
3. Pneumatique, électrotechnique, ladder IEC 61131-3
4. Vue 3D (STEP/glTF depuis SolidWorks) + co-simulation FMI
5. Déploiement local atelier : passerelle OPC UA, jumeau temps réel, IHM de supervision
6. Module diagnostic (maintenance conditionnelle puis prévisionnelle), webhooks vers GMAO

## Workflow GitHub

Le développement se fait sur des branches `vibe/<sujet>-c3546b` ; chaque lot de changements est
proposé via une pull request (revue sur GitHub avant fusion dans `main`).
