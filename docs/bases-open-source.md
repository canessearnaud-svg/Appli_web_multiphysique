# Bases open source retenues (ne pas réinventer la roue)

Recherche faite le 2026-11-27. Pour chaque besoin : le projet retenu, sa licence,
ce qu'on réutilise, et où ça s'intègre dans notre architecture.

## 1. Modélisation / visualisation 3D

| Besoin | Projet retenu | Licence | Ce qu'on réutilise | Intégration |
|---|---|---|---|---|
| Noyau CAD (géométrie STEP, assemblages, propriétés de masse) | **OpenCASCADE (OCCT)** — noyau de FreeCAD | LGPL | Lecture STEP/IGES/BREP, XCAF (assemblages), calcul masse/inertie | Côté serveur (Python via `cadquery`/`pythonocc`) pour extraire inerties depuis les modèles SolidWorks |
| Import STEP dans le navigateur | **occt-import-js** (kovacsv) ou **opencascade.js** (taucad/libcascade, OCCT 8 WASM) | MIT / Apache-ish | STEP → maillage JSON/glTF **100 % dans le navigateur**, sans serveur | Module 06 : upload du STEP SolidWorks → rendu immédiat |
| Rendu 3D web | **three.js** (ou Babylon.js) | MIT | Scène, caméra, animation des assemblages | Module 06 : la vue 3D animée par les résultats de simulation |
| Modeleur 3D dans le navigateur (plus tard) | **Chili3D** (OCCT WASM + three.js) ou **occt-wasm + brepjs** | LGPL/AGPL | Esquisse + extrusion + booléens dans le navigateur | Module 06 phase 2 : esquisser des pièces simples en ligne |
| Génération paramétrique de pièces côté serveur | **CadQuery / build123d** (Python sur OCCT) | Apache-2.0 / MIT | Scripts Python → STEP | Bibliothèque de pièces standard côté backend |
| Bibliothèque de pièces standards | **GrabCAD** (site de téléchargement de modèles) | — | Téléchargement de composants standards (vérins, raccords…) en STEP | Liens/import dans les projets |

> Note : GrabCAD n'est pas un modeleur, c'est une bibliothèque de modèles téléchargeables.
> SolidWorks reste l'outil de modélisation principal de l'utilisateur ; notre appli importe ses STEP.

## 2. Simulation multiphysique (0D/1D, par composants)

| Besoin | Projet retenu | Licence | Ce qu'on réutilise | Intégration |
|---|---|---|---|---|
| Moteur acausal + co-simulation standard | **OpenModelica + OMSimulator** (OSMC) + **PyFMI / FMPy** | OSMC license / BSD | Compilation Modelica, solveurs DAE, FMI 2.0/3.0, co-simulation SSP | Co-simulation entre nos modules et des modèles externes (FMI) |
| Bibliothèque de composants hydrauliques | **OpenHydraulics** (Modelica) / **HyLib** | — | Pompes, distributeurs, vérins, pertes de charge | Référence pour notre bibliothèque hydraulique propre (module 02) |
| Simulation multi-domain complète (fluide + méca + élec + contrôle) | **Hopsan** (Linköping, TLM) | GPL-3 | Méthode TLM, bibliothèque de composants ISO 1219, FMI | Référence principale pour les modules 02–05 ; cœur Hopsan embarquable comme service |
| Mécanique multibody 3D (si besoin au-delà de notre solveur plan) | **Project Chrono / PyChrono** | Apache-2.0 | Dynamique multibody DAE, FEA, FSI, module **Chrono::FMI** | Option pour la mécanique 3D ; notre solveur plan reste pour le schéma cinématique 2D |
| Cinématique planaire | **notre solveur** (déjà fait, testé) | — | — | Module 01 |

Décision : on garde notre éditeur + notre assembleur (l'UX web est le différenciateur), et on **réutilise les bibliothèques de composants Modelica/Hopsan via FMI** pour ne pas réécrire les lois physiques.

## 3. Automatisme (PLC IEC 61131-3)

| Projet retenu | Licence | Réutilisation |
|---|---|---|
| **Beremiz + MatIEC** | GPL | IDE + runtime PLC IEC 61131-3 (LD, FBD, ST, IL, SFC), format d'échange **PLCopen XML**, runtime intégrable, liaisons OPC UA/Modbus/MQTT |
| **OpenPLC v4** | GPL | Soft-PLC headless + éditeur, Modbus TCP |
| **SVGHMI** (Beremiz) | — | IHM web en SVG — exactement notre module supervision |

Décision : module 05 = éditeur ladder/ST dans notre appli, **compilé/exécuté par le runtime MatIEC/OpenPLC** embarqué comme service, échange de variables avec la simulation via FMI/variables partagées.

## 4. Jumeau numérique / IoT industriel (module 07)

| Besoin | Projet retenu | Licence |
|---|---|---|
| OPC UA client/serveur (Python) | **asyncua (opcua-asyncio)** | MIT |
| OPC UA embarqué (C) | **open62541** | MPL-2.0 |
| MQTT broker + Sparkplug B | **Mosquitto** / **EMQX** | EPL/EDL, Apache-2.0 |
| Bus de terrain | pymodbus, python-snap7 (S7), etc. | divers |
| Séries temporelles | **TimescaleDB** ou **InfluxDB** | Apache-2.0 |
| Tableaux de bord | **Grafana** (embed) | AGPL |

## 5. GMAO (module 08, intégration uniquement)

**GLPI** (+ plugin maintenance), **OpenMaint**, **Snipe-IT** — on ne développe pas de GMAO, on pousse des alarmes/tickets par API/webhooks.

## 6. Notre propre code (déjà fait, on garde)

- Solveur cinématique planaire + éditeur liaison-d'abord (module 01)
- File de jobs, multi-utilisateurs, API FastAPI, WebSocket
- Schémas JSON par domaine, runs, résultats

## Règle

Avant chaque module : chercher ici d'abord. On n'intègre un projet externe que s'il est
maintenu, licencié proprement (MIT/Apache/LGPL/MPL de préférence), et intégrable dans
notre architecture (service Docker, bibliothèque Python/JS, ou FMI).
