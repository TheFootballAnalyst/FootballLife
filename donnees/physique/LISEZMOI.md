# Profils physiques — version corrigée

Extraction du **jeu de données EA FC 26** (16 228 joueurs), figée au
**16 septembre 2026**. Ne pas ré-extraire en cours de saison : les notes EA
changent chaque semaine et la valeur des cartes bougerait sans raison de jeu.

## Quatre corrections depuis la version précédente

**Le pied fort était inversé.** Le code 1 d'EA vaut *droitier*, le 2
*gaucher* — vérifié sur Messi et Salah à 2, Mbappé et Kane à 1. Le tableau
faisait l'inverse. **C'est corrigé à la source** : si `PIED_EA` compensait
l'erreur côté import, il faut le remettre à l'endroit dans le même commit.

**Le complément porte désormais les mêmes colonnes** que la première passe :
`naissance`, `poste`, `championnat`, `note`. En-têtes strictement identiques,
les deux fichiers se concatènent.

**542 joueurs récupérés au lieu de 480**, grâce à trois corrections
d'appariement : les apostrophes soudées (« N'Dicka » donne « ndicka »), les
patronymes composés (« Thuram-Ulien » rejoint « Thuram »), et un filtre par
ligne de terrain qui tranche les homonymes — un gardien ne peut pas être
apparié à un attaquant.

**55 identifiants EA partagés résolus.** Quand deux joueurs pointaient le même
EA, on garde celui dont le nom colle le mieux. Il n'en reste que deux, dans
`audit_suspects.csv`.

## Couverture

| temps de jeu | couverture |
|---|---|
| au-delà de 900 min | **92 %** (2 489 / 2 699) |
| au-delà de 1800 min | **95 %** (1 580 / 1 655) |
| au-delà de 2700 min | **97 %** (749 / 772) |

**7 134 profils au total.** Les 158 absents à plus de 900 minutes jouent à
Tondela, Rio Ave ou Telstar : EA ne couvre pas ces divisions, la donnée
n'existe nulle part. Leur donner `defauts_par_poste.json`.

## Fichiers

| fichier | contenu |
|---|---|
| `physique_joueurs.csv` | 6 592 profils, première passe |
| `physique_complement.csv` | 542 profils, seconde passe, même en-tête |
| `defauts_par_poste.json` | médianes par poste pour les joueurs sans profil |
| `mesures_fotmob_ucl.json` | 583 joueurs **mesurés** en Ligue des champions |
| `physique_toujours_absents.csv` | 2 521 sans profil, dont 158 à plus de 900 min |
| `audit_suspects.csv` | 2 cas restants à trancher à l'œil |

## Calibration

Corrélations vérifiées entre notes EA et mesures réelles :

| note EA | mesure | corrélation |
|---|---|---|
| `endurance` | distance par 90 min | **+0,81** |
| `vitesse_pointe` | vitesse de pointe réelle | **+0,78** |
| `acceleration` | sprints par 90 min | **+0,75** |

**10 points de note EA valent 1,41 km/h réels.**

## Trois pièges

**Les gardiens sont faussés** : leur vitesse n'est pas mesurable en match, ils
ne sprintent jamais. Les exclure de toute calibration.

**Les championnats mineurs sont sous-notés** par manque d'attention d'EA, pas
par mesure.

**Les homonymes.** 39 faux positifs ont été retirés à la main après quatre
tentatives d'automatisation : aucune règle ne sépare « Joe » pour « Joseph »,
légitime, de « Eric » pour « Guilherme », qui ne l'est pas. Relancer
`audit_physique.py` après tout nouvel import.
