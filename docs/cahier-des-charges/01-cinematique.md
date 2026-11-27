# Spec module 01 : Schéma cinématique + simulation de mécanismes

Référence : [schema-cinematique.com](https://schema-cinematique.com/) (analyse faite le 2026-11-27).

## Objectif

Dessiner un schéma cinématique (liaisons normalisées + solides), l'analyser
(mobilité / hyperstatisme) et le simuler (animation + courbes), en 2D puis 3D.

## Agencement de l'écran

```
+------------------------------------------------------------------+
| ← projets | nom du projet | Enregistrer | Analyser (m,h) | ▶ Simuler | ⏹ | zoom |
+----------+---------------------------------------+-------------+
| palette  |                                       | inspecteur  |
| - Select |        canvas 2D (ou 3D)              | - propriétés|
| - Pivot  |                                       |   de la     |
| - Gliss. |                                       |   sélection |
| - ...    |                                       | - liste des |
|          |                                       |   solides   |
|          |                                       |   (couleur, |
|          |                                       |   nom, nb de|
|          |                                       |   liaisons) |
|          |                                       | - moteur ω  |
|          |                                       | - analyse   |
+----------+---------------------------------------+-------------+
| courbes de simulation (sous le canvas)                           |
+------------------------------------------------------------------+
```

## Fonctionnalités

### Édition (dessin)
- [x] **F1 — Poser une liaison au clic** : le clic = centre exact de la liaison, éditable en x/y (m, au mm).
- [x] **F2 — Relier 2 liaisons → solide** : outil « Relier », clic liaison 1 puis liaison 2 ; le solide apparaît (trait + nom + couleur auto).
- [x] **F3 — Bâti** : attacher une liaison au solide fixe « BÂTI ».
- [x] **F4 — Types de liaison v1** : pivot, glissière (axe réglable), encastrement.
- [ ] **F5 — Palette ISO 3952 complète** : hélicoïdale, pivot glissant, rotule, appui plan, sphérique, etc.
- [ ] **F6 — Éléments de transmission** : engrenages, poulies/courroies, chaîne, came, frein, accouplement, vérin.
- [x] **F7 — Déplacer / supprimer** : déplacer une liaison (le solide suit), supprimer liaison ou solide.
- [ ] **F8 — Annuler/rétablir (Ctrl+Z/Y), copier/coller/dupliquer, tout sélectionner.**
- [ ] **F9 — Grille + aimantation (15° avec Maj, sans grille avec Alt).**
- [ ] **F10 — Raccourcis clavier** (1–9 = liaisons, L = relier, M = moteur, V = sélection…).
- [ ] **F11 — Nommage** : renommer solides et liaisons (clic sur le + au survol).

### Analyse
- [x] **F12 — Mobilité m et hyperstatisme h** (Grübler plan), Σ contraintes, liste des liaisons.
- [ ] **F13 — Graphe des liaisons** (classes d'équivalence en nœuds, liaisons en arêtes) + suggestion de remplacement si h > 0.

### Simulation
- [x] **F14 — Moteur** : ω réglable (rad/s) sur un solide mobile.
- [x] **F15 — Animation en boucle** + bouton stop ; arrêt auto à la moindre édition.
- [x] **F16 — Courbe de l'angle du solide moteur** vs temps.
- [ ] **F17 — Trajectoires (drapeaux)** : poser un drapeau sur un point → courbe de sa trajectoire.
- [ ] **F18 — Sondes** : valeur d'une liaison (angle, course) en courbe.
- [ ] **F19 — Dynamique** : masses/inerties des solides, forces aux liaisons, équilibrage.
- [x] **F20 — Assemblage robuste** : le solveur s'ancre sur le dessin (pas d'effondrement, pas de saut de branche).

### Études statique et dynamique (ajout demandeur, 2026-11-27)
- [ ] **F26 — Moteur linéaire (vérin linéaire)** : drive une glissière en position/vitesse imposée `x(t) = x0 + v·t` (effort imposé en v2) ; course, vitesse, accélération tracées.
- [ ] **F27 — Masses et inerties** par solide (saisie manuelle d'abord ; import automatique depuis le STEP SolidWorks via OCCT au module 06).
- [ ] **F28 — Accélérations** des solides (q̈) : courbes + vecteurs sur le schéma animé.
- [ ] **F29 — Efforts dans les liaisons** : forces de réaction aux pivots (2 composantes), effort axial en glissière, calculés par les multiplicateurs de Lagrange λ du système KKT `[M  −Jᵀ ; J  0]·[q̈ ; λ] = [Q_ext + h ; −ḊJ·q̇]` (Newton–Euler contraint).
- [ ] **F30 — Couples et puissance** : couple moteur C(t), puissance P = C·ω (rotatif) ou P = F·v (linéaire), courbes + affichage en direct sur le schéma.
- [ ] **F31 — Étude statique** : gravité + effort extérieur imposé sur un solide, avec q̇ = q̈ = 0 → torseur de réaction dans chaque liaison (résolution du même système KKT à l'équilibre).
- [ ] **F32 — Bilan de puissance** : puissance motrice vs somme des puissances aux liaisons → rendement du mécanisme.

### Vues et fichiers
- [x] **F21 — Zoom / panoramique** du canvas.
- [x] **F22 — Sauvegarde par projet** (rechargée à l'ouverture).
- [ ] **F23 — Vue 3D** du mécanisme (orbite, plan de travail).
- [ ] **F24 — Export SVG / PNG / image copiable.**
- [ ] **F25 — Bibliothèque d'exemples** (quatre-barres, bielle-manivelle, etc.).

## Données

Schéma = JSON `{ solids, joints, motor | linearMotor, groundId }` stocké dans la table
`diagrams` (domaine `kinematics`), converti côté serveur en modèle multibody
(`toBackendDiagram` → `Mechanism`). Chaque solide peut porter `mass` et `inertia`
(F27). Simulations = runs (table `runs`).

## Hors périmètre

Modélisation 3D de pièces (voir module 06), dynamique flexible (FEM), liaisons avec jeu.
