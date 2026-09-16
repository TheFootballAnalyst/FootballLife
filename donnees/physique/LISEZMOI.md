# Profils physiques — état des lieux

## Ce qu'il y a dedans

| fichier | contenu |
|---|---|
| `physique_joueurs.csv` | 6 592 profils, première passe (nom complet) |
| `physique_complement.csv` | 480 profils, seconde passe (noms d'usage, diacritiques, clubs) |
| `defauts_par_poste.json` | médianes par poste, pour les joueurs sans profil |
| `mesures_fotmob_ucl.json` | 583 joueurs **réellement mesurés** en Ligue des champions |
| `physique_toujours_absents.csv` | 2 636 joueurs sans profil, dont 169 à plus de 900 min |
| `audit_suspects.csv` | 30 identifiants EA partagés, à trancher à l'œil |

Les deux CSV de profils se concatènent : même en-tête, indexés sur
`fotmob_id`. Total **7 072 profils**.

## Les colonnes

`acceleration`, `vitesse_pointe`, `agilite`, `equilibre`, `reactions`,
`endurance`, `force`, `detente`, `agressivite` — sur 1 à 99, échelle EA FC 26.
`taille_cm`, `poids_kg` pour la masse. `pied_fort` (Left/Right),
`mauvais_pied` et `gestes` de 1 à 5 étoiles. Plus `age` et `naissance`.

## Couverture

85 % des joueurs au-delà de 900 minutes, 88 % au-delà de 1800, 90 % pour les
titulaires réguliers. Les absents jouent en moyenne 270 minutes, dans des
championnats qu'EA ne couvre pas (Tondela, Rio Ave, Telstar).

**Pour eux, utiliser `defauts_par_poste.json`** plutôt qu'une valeur neutre :
un ailier inconnu prend 77 d'accélération, pas 50.

## Calibration — la partie qui compte

`mesures_fotmob_ucl.json` contient des mesures **réelles** issues du suivi
FotMob en Ligue des champions : vitesse de pointe en km/h, distance parcourue,
distance en sprint, nombre de sprints, le tout ramené à 90 minutes.

Corrélations vérifiées entre notes EA et mesures :

| note EA | mesure | corrélation |
|---|---|---|
| `endurance` | distance par 90 min | **+0,81** |
| `vitesse_pointe` | vitesse de pointe réelle | **+0,78** |
| `acceleration` | sprints par 90 min | **+0,75** |

**Conversion mesurée : 10 points de note EA valent 1,41 km/h réels.** C'est
la relation à utiliser pour transformer les notes en vitesses du moteur.

## Trois pièges

**Les gardiens sont faussés.** Leur vitesse réelle n'est pas mesurable en
match — ils ne sprintent jamais. Les six joueurs les plus surestimés par EA
sont tous des gardiens. Les exclure de toute calibration.

**Les championnats mineurs sont sous-notés.** EA note bas par manque
d'attention, pas par mesure. Un joueur de Pro League y perd quelques points.

**Les homonymes ont coûté cher.** 37 faux positifs ont été retirés à la main
après trois tentatives d'automatisation ratées : aucune règle ne sépare
« Joe » pour « Joseph », légitime, de « Eric » pour « Guilherme », qui ne
l'est pas. Relancer `audit_physique.py` après tout nouvel import.

## Les scripts

```
python3 importe_ea.py --dossier kaggle --db moteur/fotmob_2526.db
python3 complete_physique.py --manquants manquants.csv --dossier kaggle
python3 audit_physique.py --fichiers physique_joueurs.csv physique_complement.csv --db moteur/fotmob_2526.db
```

Source : jeu de données EA FC 26 (16 228 joueurs), à figer à une date donnée.
Les notes changent chaque semaine pendant la saison ; sans version figée, la
valeur des cartes bougerait sans raison de jeu.
