# Cahier des charges de l'application

## Méthode de travail

Chaque module de l'application a **son propre fichier de spec** dans ce dossier
(`01-cinematique.md`, `02-hydraulique.md`, …). On travaille module par module :

1. **Écrire/valider la spec** avec le demandeur (fonctionnalités cochables `[ ]`,
   critères d'acceptation, hors périmètre).
2. **Développer** sur une branche `vibe/<module>-c3546b`, avec tests.
3. **PR + revue** (bouton « Merge pull request » sur GitHub).
4. **Cocher la spec** (`[x]`) dans le même commit que la fonctionnalité, pour que le
   document reflète toujours l'état réel du logiciel.

Règles : une spec décrit **ce que voit l'utilisateur** (écrans, agencement, boutons,
comportements), pas le code. Toute fonctionnalité livrée sans être dans la spec est
refaite proprement. Le template est dans `template.md`.

## Modules prévus

| Fichier | Module | État |
|---|---|---|
| `01-cinematique.md` | Schéma cinématique 2D/3D + simulation de mécanismes | spec écrite, v2 en développement |
| `02-hydraulique.md` | Circuits hydrauliques 0D (ISO 1219) | à écrire |
| `03-pneumatique.md` | Circuits pneumatiques | à écrire |
| `04-electrotechnique.md` | Circuits électriques | à écrire |
| `05-automatisme.md` | Automate IEC 61131-3 (ladder/ST) | à écrire |
| `06-vue-3d.md` | Vue 3D animée (import STEP/glTF depuis SolidWorks) | à écrire |
| `07-jumeau-numerique.md` | Jumeau temps réel (OPC UA/Modbus), supervision IHM, diagnostic | à écrire |
| `08-gmao.md` | Lien vers GMAO (webhooks, pas de GMAO intégrée) | à écrire |

## Références externes

- [schema-cinematique.com](https://schema-cinematique.com/) — référence pour le module cinématique (palette ISO 3952, relier les liaisons, solides auto-colorés, vues 2D/3D, m/h, simulation moteur/trajectoires/sondes).
- Automation Studio (Famic Technologies) — référence pour les modules fluides/élec/automatisme (schémas ISO 1219, bibliothèques de composants).
- ISO 3952 (symboles de liaisons cinématiques), ISO 1219 (symboles fluides).
