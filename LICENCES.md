# Licences des ressources

## Code source

Le code de ZONE DE FRAPPE (Python et shaders GLSL) est fourni sous licence **MIT**.

## Ressources graphiques et audio

**Toutes les ressources du jeu sont produites par le projet lui-même**, par calcul, à partir du code source :

| Dossier | Contenu | Origine | Licence |
|---|---|---|---|
| `assets/textures/` | 29 matériaux PBR (albédo + normale/rugosité/métal, 512×512) | `graphics/textures.py` (bruits fractals, motifs paramétriques) | CC0 1.0 (domaine public) |
| `assets/models/` | 33 modèles OBJ (drones, émetteurs, voitures, arbres, mobilier urbain…) | `graphics/models.py` (modélisation procédurale) | CC0 1.0 (domaine public) |
| `assets/audio/` | 39 sons et musiques WAV (effets, ambiances, 2 musiques) | `audio/synth.py` (synthèse : oscillateurs, bruit filtré, réverbération) | CC0 1.0 (domaine public) |

Aucune ressource tierce (image, son, modèle, police, musique) n'est incluse dans le projet.

## Polices

L'interface utilise les polices système **Bahnschrift**, **Segoe UI** ou **Arial**. Elles sont fournies avec Windows et ne sont **pas** redistribuées dans le projet. Sur une machine où elles manquent, pygame utilise sa police par défaut.

## Bibliothèques (installées via pip, non incluses)

| Bibliothèque | Licence |
|---|---|
| pygame | LGPL 2.1 |
| ModernGL | MIT |
| NumPy | BSD 3-Clause |

## Remplacer une ressource

- **Modèles** : remplacez un fichier `assets/models/<nom>.obj` par votre propre OBJ (exporté depuis Blender, par exemple). Les groupes `usemtl` doivent porter les noms des matériaux du jeu (`paint`, `brushed`, `polymer`, `emissive`, `glass`…) ; une couleur de sommet optionnelle est lue au format `v x y z r g b`.
- **Textures** : remplacez `<matériau>_albedo.png` ou `<matériau>_normal.png` (RGBA ; pour la carte normale : RG = normale, B = rugosité, A = métal).
- **Sons** : remplacez le WAV portant le même nom (44,1 kHz, stéréo, 16 bits).
