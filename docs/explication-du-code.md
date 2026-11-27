# Explication du code, pour non-informaticiens

Ce document explique **quoi** fait chaque partie du logiciel et **comment**, en français
courant, sans jargon. Le code lui-même reste « propre » (sans commentaires) : toute
l'explication est ici, dans `docs/`.

> Pour lire ce fichier joliment sur GitHub : onglet **Code** → dossier `docs` →
> clique sur `explication-du-code.md`.

---

## 1. Les technologies choisies, et pourquoi

| Choix | C'est quoi ? | Pourquoi ce choix |
|---|---|---|
| **React + TypeScript + Vite** (frontend) | La partie visible dans ton navigateur | Standard du web moderne ; TypeScript attrape les erreurs avant l'exécution |
| **Python + FastAPI** (backend) | Le « serveur » qui calcule et stocke | Python est la langue de la science (numpy, scipy, solveurs) ; FastAPI est moderne et auto-documenté (`/docs`) |
| **PostgreSQL** | La base de données (utilisateurs, projets, schémas, runs) | Solide, gratuite, standard industriel |
| **Redis + RQ** | La « file d'attente » des simulations | Chaque simulation est un job isolé → plusieurs utilisateurs simultanés sans conflit |
| **WebSocket** | Le « tuyau » qui pousse les résultats en direct dans le navigateur | Les courbes se remplissent en direct pendant le calcul |
| **NumPy** | Calcul matriciel en Python | Le solveur cinématique en a besoin |
| **Docker Compose** | Lance tout (base + serveur + worker + appli) en une commande | « Ça marche chez toi comme chez moi », pas d'installation manuelle |
| **GitHub + branches + PR** | Gestion des versions | Chaque évolution est reviewée avant d'être fusionnée dans `main` |

## 2. L'arborescence du dépôt, expliquée

```
Appli_web_multiphysique/
├── docker-compose.yml        # la recette qui lance les 5 « conteneurs »
├── README.md                 # démarrage rapide + architecture
├── docs/                     # TOUTE la documentation (celle-ci, les specs, les bases open source)
├── backend/                  # le serveur (Python)
│   ├── app/
│   │   ├── main.py           # l'API : les routes (ex. POST /api/projects, GET /api/runs/{id}, WebSocket)
│   │   ├── auth.py           # connexion par jeton (mode dev : un e-mail suffit)
│   │   ├── models.py         # les tables de la base (users, projects, diagrams, runs)
│   │   ├── schemas.py        # le format des données échangées avec le navigateur
│   │   ├── queue.py          # la file d'attente Redis
│   │   ├── worker.py         # le processus qui exécute les simulations
│   │   └── sim/              # LE MOTEUR DE SIMULATION
│   │       ├── engine.py     # reçoit un run, choisit le bon module, stocke le résultat
│   │       └── mechanics/kinematics.py   # solveur de schémas cinématiques (voir §5)
│   └── tests/                # les tests automatiques (pytest)
└── frontend/                 # la partie navigateur (React)
    └── src/
        ├── api.ts            # les appels au serveur
        ├── pages/            # les écrans : Login, Projects, KinematicsEditor
        └── kinematics/model.ts  # le modèle du schéma cinématique + conversion vers le solveur
```

## 3. Le trajet d'une simulation, étape par étape

Quand tu cliques sur **« ▶ Simuler »** :

1. Le navigateur envoie `POST /api/projects/{id}/runs` avec le schéma en JSON
   (`frontend/src/pages/KinematicsEditor.tsx` → `api.ts` → `main.py`).
2. `main.py` crée une ligne dans la table `runs` (statut `queued`) et pousse le job
   dans la file Redis (`queue.py`).
3. Le **worker** (`worker.py`) prend le job, passe le run à `running`, appelle
   `sim/engine.py` → `run_job`.
4. Le moteur convertit le schéma JSON en « mécanisme » Python
   (`kinematics.mechanism_from_dict`) puis le résout (`run_mechanism`) — voir §5.
5. Le worker publie les étapes sur le canal Redis `run:{id}` ; le WebSocket
   (`/ws/runs/{id}` dans `main.py`) les retransmet au navigateur.
6. Le résultat final (séries temporelles) est stocké dans `runs.result` (statut `done`).
7. Le navigateur interroge `GET /api/runs/{id}` toutes les 400 ms et anime le mécanisme.

## 4. La base de données (4 tables)

| Table | Contenu | Pourquoi |
|---|---|---|
| `users` / `sessions` | comptes + jetons de connexion | multi-utilisateurs |
| `projects` | les projets (avec `owner_id`) | chaque utilisateur ne voit que les siens |
| `diagrams` | les schémas enregistrés par domaine (`kinematics`, `hydraulics`…) en JSON | la sauvegarde |
| `runs` | les simulations (type, paramètres, statut, résultat JSON) | l'historique des calculs |

## 5. Le solveur cinématique, expliqué simplement

Fichier : `backend/app/sim/mechanics/kinematics.py`.

**L'idée** : un mécanisme = des solides rigides reliés par des liaisons. Chaque solide a
une pose `q = (x, y, θ)`. Chaque liaison (pivot, glissière…) impose des **équations de
contrainte** `Φ(q) = 0` (ex. pivot : « les deux points coïncident » → 2 équations).

**La résolution** :

1. **Position** : on résout `Φ(q) = 0` par la méthode de Newton (on linéarise, on corrige,
   on recommence). Le jacobien (les dérivées) est **analytique** (calculé à la main, pas
   numériquement) → rapide et précis.
2. **Robustesse** : si Newton échoue (dessin approximatif), on passe en
   **Levenberg–Marquardt avec ancrage au dessin** : on minimise `‖Φ(q)‖² + μ‖q − q_dessiné‖²`
   en faisant décroître μ par paliers (continuation). Comme ça, le mécanisme s'assemble
   **au plus près de ce que tu as dessiné** — pas d'effondrement au centre, pas de saut
   sur l'assemblage « miroir ». Un dernier passage de Newton affine à 1e-10.
3. **Vitesses** : en dérivant les contraintes : `J·q̇ = −∂Φ/∂t` → on résout un système
   linéaire à chaque pas.
4. **Temps** : on balaie le temps `t` de 0 à une période ; à chaque pas, on part de la
   solution précédente (démarrage à chaud → très rapide).

**Analyse structurelle** (`analyze_structure`) : compte les solides N et les liaisons,
puis formule de Grübler planaire : `m = 3(N−1) − Σc` (mobilité), `h = max(0, Σc − 3(N−1))`
(hyperstatisme). Un pivot/glissière enlève c = 2 degrés de liberté, un encastrement c = 3.

## 6. Comment vérifier que tout marche (les tests)

```bash
cd backend
python -m pytest tests -q
```

Chaque test construit un mécanisme connu (quatre-barres, bielle-manivelle), le simule et
vérifie : la boucle se ferme, le résidu des contraintes est ~0, l'assemblage reste près
du dessin, etc. Côté navigateur : `cd frontend && npx tsc --noEmit` (vérifie les types).

## 7. Glossaire rapide

- **API** : les « guichets » du serveur (des adresses comme `/api/projects`).
- **JSON** : format de texte simple pour échanger des données (le schéma = un JSON).
- **DAE** : équations différentielles + algébriques (nos contraintes) — ce que le solveur mange.
- **Job / worker** : une tâche confiée à un processus isolé.
- **PR (pull request)** : proposition de modification, reviewée avant fusion.

## 8. Où poser des questions

Dans les commentaires de la PR concernée sur GitHub, ou ici même : je réponds et
j'enrichis ce document au fur et à mesure.
