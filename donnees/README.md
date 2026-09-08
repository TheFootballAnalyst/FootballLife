# Données hors dépôt

Trois choses ne sont pas dans Git, par taille ou par droits :

| quoi | taille | où la mettre |
|------|--------|--------------|
| `fotmob.db` (une base par saison) | 300–550 Mo | `moteur/fotmob.db` |
| `cache/matches/*.json` (feuilles de match) | plusieurs centaines de Mo | `moteur/cache/matches/` |
| polices, portraits, écussons | quelques Mo | `moteur/*.ttf`, `moteur/images/` |

Tout cela est ignoré par `.gitignore`. Le moteur les lit à côté de lui
(`DB_PATH`, `CACHE_MATCHES` dans `topsflops.py`).

## Pourquoi pas dans Git

GitHub refuse tout fichier de plus de 100 Mo et avertit dès 50 Mo. Git LFS
lève cette limite mais chaque révision de la base compte dans le quota
(1 Go gratuit, stockage et bande passante), qu'une seule saison épuise.
Une base SQLite n'a pas non plus de diff utile : chaque mise à jour
hebdomadaire serait un nouveau fichier complet.

## Ce qui marche : une *release* GitHub

Un fichier joint à une release peut faire jusqu'à 2 Go, sans quota de
bande passante, sur un dépôt privé comme public. C'est le bon endroit pour
un instantané de saison, celui dont le backtest a besoin.

1. Compresser, une base SQLite se réduit de 4 à 6 fois :
   ```
   xz -T0 -6 -k fotmob.db          # -> fotmob.db.xz
   ```
   (`xz` est dans tout Linux/macOS ; sous Windows, 7-Zip produit du `.xz`.)
2. Sur GitHub : *Releases → Draft a new release*, tag `data-2025-26`,
   joindre `fotmob.db.xz`. Même chose pour le cache : `tar cJf
   cache-2025-26.tar.xz cache/matches`.
3. Récupérer d'un côté ou de l'autre :
   ```
   python3 donnees/telecharger.py https://github.com/TheFootballAnalyst/FootballLife/releases/download/data-2025-26/fotmob_2526.7z
   python3 donnees/telecharger.py https://github.com/TheFootballAnalyst/FootballLife/releases/download/data-2025-26/cache.7z
   ```
   Le script décompresse et dépose les fichiers dans `moteur/`
   (`.7z` demande `pip install py7zr` ; `.xz`, `.gz` et `.tar.*` passent
   avec la bibliothèque standard). La release `data-2025-26` contient
   `fotmob_2526.7z` (57 Mo, base de 452 Mo) et `cache.7z` (38 Mo, 3 963
   feuilles de match sous `cache/matches/`).

Pour la base *vivante* de la saison en cours, mise à jour chaque semaine,
la release n'est pas le bon outil : elle vivra sur la machine qui fait
tourner le jeu, sauvegardée après chaque journée (voir `docs/ROADMAP.md`,
phase 4).

## Si tu préfères un autre hébergement

Google Drive, Dropbox, un bucket S3/R2 : n'importe quel lien direct
convient au même script. Il faut juste que l'URL renvoie le fichier et non
une page HTML (Drive demande un lien « export=download »).
