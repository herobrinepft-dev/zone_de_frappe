# ZONE DE FRAPPE

Jeu de tir à la première personne en 3D temps réel (Python + OpenGL 3.3) : vous défendez un
centre-ville d'entraînement de 420 × 420 m contre dix vagues de **drones d'entraînement fictifs**.

Missions variées (élimination, défense de balise, collecte de données), trois émetteurs
améliorables, cosmétiques, progression par niveaux, quatre opérations (aube brumeuse, plein midi,
orage au crépuscule, nuit) et trois niveaux de difficulté.

---

## 1. Installation (Windows, macOS, Linux)

### Prérequis
- **Python 3.11 ou plus récent** — https://www.python.org/downloads/
  (sous Windows, cochez « Add Python to PATH » pendant l'installation).
- Une carte graphique compatible **OpenGL 3.3** (toute carte des dix dernières années).

### Étapes
1. Décompressez l'archive `zone_de_frappe.zip`.
2. Ouvrez un terminal dans le dossier `zone_de_frappe`.
3. Installez les dépendances :
   ```
   python -m pip install -r requirements.txt
   ```
4. Lancez le jeu :
   ```
   python main.py
   ```

**Sous Windows, le plus simple** : double-cliquez sur `LANCER_LE_JEU.bat`. Il installe les
dépendances si nécessaire, puis démarre le jeu.

Le premier lancement crée les ressources manquantes (environ 15 s). Les lancements suivants
chargent le cache en environ 3 s.

### Options de lancement
| Commande | Effet |
|---|---|
| `python main.py` | Lancement normal |
| `python main.py --window 1280x720` | Force une fenêtre de taille donnée |
| `python main.py --autotest` | Exécute la batterie de tests automatiques (voir § 6) |

---

## 2. Commandes

| Touche | Action |
|---|---|
| **Z Q S D** / **W A S D** / flèches | Se déplacer (les claviers AZERTY et QWERTY sont pris en charge) |
| **Souris** | Regarder |
| **Clic gauche** | Tirer |
| **Clic droit** | Visée précise (lunette sur le FAUCON) |
| **Maj** | Sprint (consomme l'endurance) |
| **Espace** | Sauter |
| **Ctrl** / **C** | S'accroupir |
| **1 2 3** / molette | Changer d'émetteur (parmi ceux possédés) |
| **Échap** | Pause (reprendre, paramètres, abandonner) |
| **F11** | Plein écran / fenêtré |
| **F12** | Capture d'écran (dossier `screenshots/`) |
| **Entrée** (menu) | Déployer |

---

## 3. Contenu du jeu

### Menu principal
**ACCUEIL**, **JOUER**, **ARMURERIE**, **OPÉRATIONS**, **PARAMÈTRES**, **STATISTIQUES**, **QUITTER**.
Le fond est la ville en 3D, filmée par une caméra cinématique en orbite, avec des drones en
patrouille. Les pages s'enchaînent par glissement et fondu ; les boutons réagissent au survol
(animation et son).

### Armurerie
Présentoir 3D éclairé où l'émetteur sélectionné tourne sur un socle. Vous y trouvez ses
statistiques (dégâts, cadence, précision, portée, dissipation), trois améliorations à trois
niveaux chacune, 7 finitions et 5 couleurs de faisceau, débloquées avec les crédits gagnés en partie.

| Émetteur | Rôle | Déblocage |
|---|---|---|
| PULSAR MK-II | Automatique polyvalent | Dès le départ |
| FAUCON LR-7 | Longue portée, lunette | Niveau 3 + 2 500 CR |
| TEMPÊTE SG-4 | Dispersion (9 impulsions) | Niveau 5 + 4 000 CR |

### Drones d'entraînement
| Type | Comportement |
|---|---|
| **Éclaireur** | Rapide, fait des piqués sur le joueur et tire des rafales légères |
| **Sentinelle** | Plane à distance, tire des orbes plus lourds |
| **Blindé** | Lent et très résistant ; ses orbes explosent à l'impact (dégâts de zone) |

Les drones contournent les immeubles, s'évitent entre eux, anticipent vos déplacements (plus ou
moins selon la vague) et ne tirent que s'ils ont une ligne de vue. Leurs orbes sont visibles et
esquivables.

### Missions et progression
- **10 vagues** de difficulté croissante. Chaque vague propose une mission : *élimination*,
  *défense de balise* (tenir une zone pendant que les drones la disputent) ou *collecte* (trois
  modules de données dispersés en ville).
- Score avec **multiplicateur de combo** (jusqu'à ×5), kits de réparation et bonus de surcharge
  largués par les drones.
- **Barre d'intégrité** : régénération lente entre deux vagues, alerte cardiaque sous 30 %.
- XP → niveaux (qui débloquent opérations et émetteurs), crédits → achats à l'armurerie.
- Statistiques persistantes : parties, victoires, précision, distance, drones par type, etc.

### HUD
Mini-carte qui tourne avec le joueur (drones, objets, objectifs), panneau d'objectif avec barre de
progression, vague et chronomètre, score et combo, fil des éliminations, barre d'intégrité
segmentée, endurance, chaleur de l'émetteur, réticule dynamique (dispersion), marqueurs de touche
et d'élimination, arcs indiquant la direction des dégâts, marqueurs d'objectifs à l'écran avec
leur distance, bannières de vague, compteur d'images par seconde.

---

## 4. Technique

- **Rendu** : ModernGL (OpenGL 3.3 core), pipeline HDR en float16.
  - Matériaux **PBR** (GGX / Smith / Schlick) avec *texture arrays* : albédo + normale + rugosité + métal.
  - **Ombres dynamiques** : shadow map orthographique stabilisée (alignée sur les texels), filtrage PCF.
  - **Ciel dynamique** : cycle jour/nuit, soleil et lune, nuages procéduraux animés, étoiles scintillantes.
  - **Brouillard de hauteur** et **lumière volumétrique** (lancer de rayons dans la shadow map, rayons crépusculaires).
  - Jusqu'à 24 **lumières dynamiques** : lampadaires la nuit, tirs, explosions, feux des drones.
  - **Fenêtres allumées** la nuit (aléatoires par pièce), vitres réfléchissant le ciel.
  - **Météo** : pluie, chaussée mouillée avec flaques réfléchissantes et ondulations, éclairs et tonnerre.
  - **Végétation** animée par le vent (arbres, haies, herbes hautes à découpe alpha).
  - **Particules** : étincelles, fumée, débris, ondes de choc, faisceaux, poussières en suspension.
  - **Post-traitement** : bloom, tone mapping ACES, vignettage, effets de dégâts, FXAA.
- **Optimisation** : *frustum culling* par blocs de la ville (8×8) et des objets dynamiques
  (vectorisé), culling dédié pour la passe d'ombre, géométrie statique fusionnée (≈ 725 000
  triangles en 64 blocs), textures et modèles mis en cache, interface envoyée au GPU sans copie,
  4 préréglages de qualité (ombres, textures, volumétrique, particules, distance d'affichage,
  résolution interne).
- **Ville** : génération procédurale à graine fixe. Immeubles de 4 styles de façade avec
  rez-de-chaussée commerciaux, auvents, corniches, acrotères, tours en retrait et antennes ;
  équipements de toit, routes marquées, passages piétons, trottoirs, lampadaires, feux tricolores,
  bancs, poubelles, bornes, voitures garées ou abandonnées, parcs avec fontaine, place centrale
  avec monument, chantier de conteneurs, ligne d'horizon lointaine.
- **Audio** : pygame.mixer, sons positionnels (panoramique et atténuation), boucles d'ambiance
  (ville, pluie, bourdonnement des drones), musiques de menu et de jeu en fondu enchaîné.

### Performances mesurées (RTX 4060, 1600×900, qualité Élevé)
Environ 90 à 100 images/s en combat ; chargement en environ 3 s (avec le cache).

---

## 5. Organisation du projet

```
zone_de_frappe/
├── main.py                 point d'entrée
├── LANCER_LE_JEU.bat       lanceur Windows
├── requirements.txt
├── engine/                 application, boucle, caméra, mathématiques, chemins
├── graphics/               renderer, matériaux, textures, maillages, modèles, OBJ, particules, atmosphère
├── gameplay/               ville, collisions, joueur, émetteurs, vagues/missions, session, progression, données
├── entities/               drones, projectiles, objets ramassables
├── ui/                     thème, widgets, menu principal, HUD, paramètres
├── audio/                  synthèse des sons et musiques, gestionnaire audio
├── shaders/                GLSL (éclairage, ombres, composition, bloom, FXAA, particules, interface)
├── assets/                 textures PNG, modèles OBJ, sons WAV (générés, CC0)
├── config/                 paramètres par défaut + fichiers utilisateur (créés au premier lancement)
├── tools/                  generate_assets.py (régénération des ressources)
└── tests/                  test automatique de bout en bout
```

Les réglages (`config/user_settings.json`) et le profil (`config/profile.json`) sont sauvegardés
automatiquement. Pour repartir de zéro, supprimez ces deux fichiers.

---

## 6. Tests automatiques

```
python main.py --autotest
```

Le test pilote le **vrai jeu** comme le ferait un joueur : clics sur les vrais boutons, touches et
mouvements de souris simulés. Il enregistre des captures dans `tests/output/` et un rapport JSON.
Il utilise un profil temporaire et ne touche jamais à vos données. Il vérifie notamment :

- le démarrage, la compilation des shaders, la visibilité réelle de la scène 3D (luminance et contraste) ;
- que l'**interface transparente ne masque pas la scène** : l'image est comparée pixel à pixel
  avant et après la composition de l'interface (le HUD couvre environ 8 % de l'écran, le centre reste dégagé) ;
- chaque rubrique et chaque bouton du menu (achat, sélection, verrouillage, onglets, interrupteurs, confirmation pour quitter) ;
- les déplacements, le sprint, le pas latéral, le saut, la gravité, la rotation de la vue et l'accroupissement ;
- les collisions (impossible de traverser un immeuble, glissement le long des murs, tenue sur un toit) ;
- le tir, les dégâts infligés aux drones, l'apparition des vagues et les tirs ennemis ;
- les missions défense et collecte, la pause, le redimensionnement (3 tailles), les 4 niveaux de
  qualité (fluidité), la fin de partie, l'écran de résultats et les ambiances nuit, orage et aube.

Dernières exécutions : **95 tests sur 95 réussis** (deux passes consécutives).

---

## 7. Limites connues

- Les modèles 3D sont produits par **modélisation procédurale** (assemblages de primitives
  détaillées), pas sculptés à la main. On peut les remplacer par des OBJ réalisés dans Blender
  (voir `LICENCES.md`).
- Les reflets sur les vitres et les flaques proviennent du ciel analytique : il n'y a ni reflets
  en espace écran ni lancer de rayons.
- Les drones évitent les obstacles par sondage local, sans calcul d'itinéraire global.
- Une seule carte urbaine, déclinée en quatre ambiances (heure et météo).
