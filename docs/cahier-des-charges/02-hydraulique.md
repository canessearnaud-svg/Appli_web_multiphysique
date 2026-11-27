# Spec module 02 : Circuits hydrauliques 0D (ISO 1219)

Références : **ISO 1219-1:2012** (symboles), **ISO 1219-2** (règles de tracé),
**ISO 9461** (repères des orifices), **Automation Studio P10** (Famic Technologies),
**Hopsan** (Linköping, TLM), **OpenHydraulics** (Modelica). Voir `docs/bases-open-source.md`.

## Objectif

Dessiner un circuit hydraulique avec des symboles ISO 1219, le simuler en transitoire
(pressions, débits), poser des sondes, et **coupler le vérin à la mécanique**
(schéma cinématique du module 01) et plus tard à l'automate (module 05).

## Modèle physique (0D lumped, acausal)

- **Nœud hydraulique** (connexion de ports) = volume `V` : `dp/dt = β_eff / V · (ΣQ_entrants − dV/dt)`
  (compressibilité effective β_eff incluant l'air dissous). C'est ce qui rend le système **raide** → solveur implicite (SUNDIALS CVODE/IDA).
- **Ports** : chaque composant a des ports hydrauliques nommés (P, T, A, B…) ; variables du port : pression `p` (effort) et débit `Q` (flux). Une connexion impose `p` commun et `ΣQ = 0` au nœud.
- **Lois des composants** (v1) :
  - Orifice/étranglement/tuyau : `Q = Cd·A·sign(Δp)·sqrt(2|Δp|/ρ)` ; tuyau = orifice + inertie fluide `L·dQ/dt = Δp − R·Q`.
  - Pompe cylindrée fixe : `Q = Vg·ω` ; pompe à cylindrée variable : `Q = Vg(x)·ω` (v2).
  - Limiteur de pression : s'ouvre au-delà de `p_tarage` (orifice variable).
  - Distributeur 4/3 : selon la position du tiroir (commande : manuelle/électrique/automate), relie P/T/A/B (centre fermé/ouvert/tandem en v2).
  - Vérin double effet : `Q_A = A_cap·v`, `Q_B = A_tige·v`, `F = (A_cap·p_A − A_tige·p_B) − frottement` ; **port mécanique** (force F, vitesse v, position x) exposé vers le module 01.
  - Clapet anti-retour : laisse passer dans un sens.
  - Accumulateur (v2) : vessie, `p·V_gas^n = cte`.
  - Réservoir : nœud à `p = p_atm` (référence).

## Agencement de l'écran (même pattern que le module 01)

```
+------------------------------------------------------------------+
| ← projets | nom | Enregistrer | ▶ Simuler | ⏹ | zoom             |
+----------+---------------------------------------+-------------+
| palette  |                                       | inspecteur  |
| par      |         canvas circuit (liens entre    | - propriétés|
| catégorie|         les ports des composants)      |   du composant|
| ISO 1219 |                                       | - sondes     |
+----------+---------------------------------------+-------------+
| courbes p(t), Q(t) des sondes                                    |
+------------------------------------------------------------------+
```

- Palette par catégorie : sources (pompe, réservoir), pression (limiteur, réducteur),
  direction (distributeurs 2/2…5/3), débit (étrangleur, clapet), actionneurs (vérin, moteur),
  accessoires (accumulateur, filtre, refroidisseur), mesures (manomètre, débitmètre), lignes.
- Canvas : on pose les composants, on relie leurs **ports** par des traits (clic port → port).
- Inspecteur : paramètres du composant sélectionné (Vg, Cd·A, p_tarage, alésage, course…), sondes à poser.

## Fonctionnalités

### Bibliothèque v1 (MVP)
- [ ] **H1 — Composants v1** : réservoir, pompe fixe (Vg, ω), limiteur de pression, distributeur 4/3 (3 positions), vérin double effet (alésage, tige, course), tuyau (L, D), étranglement (Cd·A), clapet anti-retour.
- [ ] **H2 — Connexion par ports** : clic port → port ; jonction = nœud ; croix sans point = pas de connexion.
- [ ] **H3 — Symboles ISO 1219-1** dessinés en SVG (module M = 3 mm comme la norme).
- [ ] **H4 — Paramétrage** dans l'inspecteur (valeurs SI).

### Simulation
- [ ] **H5 — Assembleur acausal** : graphe de connexions → DAE → solveur implicite (CVODE/IDA), pas adaptatif.
- [ ] **H6 — Sondes** : manomètre (p à un nœud), débitmètre (Q dans une branche), position/vitesse du vérin.
- [ ] **H7 — Courbes temps réel** : p(t), Q(t), x(t) pendant la simulation (WebSocket, comme module 01).
- [ ] **H8 — Scénarios de commande** : position du distributeur en fonction du temps (table de séquencement) — en attendant le module automate.

### Couplage multiphysique
- [ ] **H9 — Vérin ↔ mécanique** : le port mécanique du vérin se branche sur une liaison du schéma cinématique (module 01) ; un run lance les deux solveurs couplés (co-simulation interne, même pas de temps).
- [ ] **H10 — Animation 3D/2D** : le vérin s'allonge dans la vue (lien module 06 plus tard).

### v2 / v3
- [ ] Accumulateur, clapet piloté, counterbalance, pompe variable, distributeurs proportionnels, centre tandem/ouvert.
- [ ] Pertes de charge linéaires/locales (diagramme de Moody simplifié), cavitation (v2).
- [ ] Couplage automate (module 05) : solénoïdes du distributeur commandés par le PLC simulé.
- [ ] Export du schéma en SVG/PNG, nomenclature (BOM) des composants.

## Données

Schéma JSON `{ components: [{id, type, params, x, y, rotation}], connections: [{from: {component, port}, to: {...}}] }`,
stocké dans `diagrams` (domaine `hydraulics`). Runs dans `runs` (type `hydraulics`).

## Hors périmètre

CFD (OpenFOAM serait le relai pour ça), thermique fluide, modèles constructeur détaillés (on reste en lois physiques paramétriques).

## Critères d'acceptation du MVP

Circuit « pompe → limiteur → distributeur 4/3 → vérin → réservoir » :
1. simulation stable (pas de divergence) sur 10 s avec pas implicite,
2. la pression monte jusqu'au tarage du limiteur puis se stabilise (vérifié en courbe),
3. inversion de la commande du distributeur → le vérin sort puis rentre (x(t) croissant/décroissant),
4. sondes p et Q posables et tracées en direct.
