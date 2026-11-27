# Spec module 09 : Exercices guidés / TP (statique & cinématique graphiques, équations visibles)

Référence : [NewECLine](https://sites.google.com/view/newecligne) (cours + exercices interactifs :
reconnaissance des contacts, schéma cinématique en ligne, statique graphique, cinématique graphique,
jeux vecteurs vitesse/accélération) ; [schema-cinematique.com](https://schema-cinematique.com/) (devoirs/rendus).

## Objectif

Un espace « exercices » pour les élèves : énoncés prêts à l'emploi, constructions graphiques
interactives, **correction automatique par le solveur** du module 01, et panneau « équations
visibles » pour relier le calcul à la main au calcul machine.

## Utilisateurs

- **Élève** : déroule un énoncé, répond (graphique ou champ texte), voit la correction.
- **Prof** : choisit les énoncés, crée des devoirs, exporte les résultats (CSV).

## Agencement

```
+------------------------------------------------------------------+
| ← projets | nom de l'exercice | Énoncé | Aide | Valider | score   |
+----------+---------------------------------------+-------------+
| énoncé   |                                       | panneau     |
| + données|         canvas exercice               | - équations |
| (schéma, |         (construction graphique        |   visibles  |
|  valeurs)|         de l'élève)                   |   (Φ, J,    |
|          |                                       |   KKT, m/h) |
+----------+---------------------------------------+-------------+
| résultat : ta réponse vs le calcul du solveur (écart en %)      |
+------------------------------------------------------------------+
```

## Fonctionnalités

### Bibliothèque d'énoncés
- [ ] **E1 — Énoncés types** : quatre-barres, bielle-manivelle, porte de bus, levier… avec schéma, données (longueurs, masses) et objectifs.
- [ ] **E2 — Mode prof** : créer/dupliquer un énoncé, activer un devoir avec lien élève, export CSV des résultats.

### Statique graphique (interactif)
- [ ] **E3 — Polygone des forces** : l'élève trace les vecteurs force à la souris ; fermeture automatique vérifiée ; comparaison avec le solveur statique (F31, module 01).
- [ ] **E4 — Funiculaire** : tracé des rayons funiculaires, fermeture au point d'application ; vérification numérique (moments).

### Cinématique graphique (interactif)
- [ ] **E5 — Vecteurs vitesse** : l'élève trace les vitesses de points ; vérification contre le solveur (q̇, module 01).
- [ ] **E6 — CIR et équiprojectivité** : l'élève place le centre instantané de rotation ; vérification (vitesse = ω × distance au CIR).

### Voir les équations (mode pédagogique)
- [ ] **E7 — Panneau « équations »** : affiche pour le mécanisme courant les contraintes `Φ(q)=0`, le jacobien `J`, la matrice KKT `[M −Jᵀ ; J 0]`, et m/h — lisibles, copiables.
- [ ] **E8 — Quiz** : questions auto-corrigées (mobilité m, hyperstatisme h, torseur d'une liaison, puissance) avec comparaison « ton calcul à la main vs le solveur ».
- [ ] **E9 — « Remplir la matrice » remplacé par** : matrices affichées avec cases surlignées à compléter mentalement + champ de réponse chiffrée (pas de saisie matricielle interactive — trop fragile).

## Données

Énoncé = JSON `{ id, titre, domaine, schema (réutilise le format module 01), donnees, objectifs, tolerance }`,
stocké en bibliothèque (table `diagrams` domaine `exercice` ou table dédiée plus tard).
Réponses élèves = table `exercise_results` (à créer), export CSV côté prof.

## Couplage avec les autres modules

- Réutilise le schéma et le solveur du **module 01** (cinématique) : la vérification graphique
  s'appuie sur F28 (vitesses/accélérations) et F31 (statique).
- Ne duplique pas l'éditeur de schéma : l'énoncé fournit le schéma ; l'élève répond.

## Hors périmètre

Saisie matricielle interactive par l'élève, vidéos intégrées, chat élèves, gamification avancée.

## Critères d'acceptation (MVP)

1. Un énoncé « quatre-barres » se déroule : schéma affiché, données, objectif clair.
2. L'élève trace un polygone des forces ; le système dit « fermé / non fermé » et compare au solveur statique (écart < tolérance).
3. Le panneau équations affiche Φ, J, KKT et m/h du mécanisme de l'énoncé.
4. Le prof voit le score de l'élève et peut exporter le CSV.
