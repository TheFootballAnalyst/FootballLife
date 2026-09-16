# Profils physiques — version consolidée

Jeu de données **EA FC 26**, figé au **16 septembre 2026**.

## Ce qui change

**Tout est rejouable.** Les corrections manuelles vivent désormais dans un
seul script, `nettoie_complement.py` : les 54 faux positifs connus, les trois
ajouts à la main, et la résolution des identifiants EA partagés par club,
poste puis patronyme. Après toute ré-extraction, la chaîne est :

```
python3 importe_ea.py --dossier kaggle --db moteur/fotmob_2526.db
python3 complete_physique.py --manquants manquants.csv --dossier kaggle --sortie physique_complement.csv
python3 nettoie_complement.py --db moteur/fotmob_2526.db
python3 audit_physique.py --fichiers physique_joueurs.csv physique_complement.csv --db moteur/fotmob_2526.db
```

**Le pied est à l'endroit dans les deux fichiers** — Salah « Left », Mbappé
« Right », vérifié. Le drapeau qui lisait la première passe à l'envers doit
passer à `False`. 5 284 droitiers, 1 849 gauchers.

**Deux bugs d'appariement corrigés** sur ta seconde liste : « Athletic Club »
se vidait entièrement à la normalisation (tous ses mots sont creux), ce qui
bloquait Jauregizar, Vivian et Guruzeta ; et les doubles patronymes espagnols
n'étaient cherchés que sur le second nom. Jauregizar, Vivian, Isi Palazón,
Yéremi Pino, Fermín López, Chabot et Guruzeta sont tous présents.

## Couverture

| temps de jeu | couverture |
|---|---|
| au-delà de 900 min | **93 %** (2 505 / 2 699) |
| au-delà de 1800 min | **96 %** (1 590 / 1 655) |
| au-delà de 2700 min | **98 %** (756 / 772) |

**7 133 profils, audit vide.** Les 153 absents à plus de 900 minutes sont
soit hors d'EA — Tondela, Telstar, Gagliardini, Tiago Gabriel, Mathew Ryan —
soit sans candidat sûr. Ils prennent `defauts_par_poste.json`.

## Fichiers

`physique_joueurs.csv` 6 575 · `physique_complement.csv` 558, **même
en-tête** · `defauts_par_poste.json` · `mesures_fotmob_ucl.json` ·
`physique_toujours_absents.csv` · quatre scripts.

## Calibration

Endurance / distance +0,81 · vitesse / vitesse réelle +0,78 · accélération /
sprints +0,75. **10 points EA = 1,41 km/h.** Gardiens à exclure.
