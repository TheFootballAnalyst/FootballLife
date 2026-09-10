# Le site — phase 3

`web/app/` : un serveur FastAPI, une base SQLite (celle de `jeu/schema.sql`),
une page HTML avec son JavaScript. Pas de compilation, pas de framework
côté navigateur. Le serveur ne calcule jamais de note : la clôture d'une
journée est `jeu/pipeline.py`, déclenchée depuis l'écran Admin.

## Écrans

| écran | ce qu'on y fait |
|---|---|
| Connexion | créer un compte (pseudo, mot de passe, nom d'équipe) ; le premier compte est administrateur |
| Marché | toutes les cartes (écussons ou liste), filtres par poste, ligue, tri (OVR, prix, OVR par M€, forme, âge, popularité), fiche joueur, achat et vente au prix public en M€ ; fermé pendant une journée verrouillée |
| Équipe | formation, onze sur le terrain, capitaine, ordre du banc, **Envoyer la composition** avant le premier coup d'envoi |
| Journée | le résultat de la dernière journée (détail par joueur, entrants du banc, rang), l'état de la journée en cours, l'historique |
| Classement | mondial, plus les ligues privées : créer une ligue donne un code, le partager suffit |
| Admin | verrouiller ou rouvrir la journée, charger les prestations notées, clôturer |

Règles appliquées côté serveur : 15 cartes au plus, 2 gardiens, 5
défenseurs, 5 milieux, 3 attaquants ; onze légal (1 gardien, 3 à 5
défenseurs, 2 à 5 milieux, 1 à 3 attaquants) ; capitaine titulaire ;
composition refusée après la clôture ; marché fermé entre la clôture et
le calcul ; prix = prix OVR × (1 + part des équipes qui possèdent la
carte), recalculé à chaque clôture.

## Lancer chez soi

```
py -m pip install fastapi "uvicorn[standard]" python-multipart
py web/app/demo.py                                   # -> jeu/demo.sqlite (saison 25/26 à partir de J26)
                                                     # construit d'abord jeu/jeu_2526.sqlite depuis
                                                     # moteur/fotmob_2526.db s'il n'existe pas (1 min 30)
py web/app/lancer.py                                 # sert http://localhost:8000 sur la base de démo
```

`lancer.py` choisit la base (`jeu/demo.sqlite` si elle existe), génère et
garde un secret de session dans `jeu/.secret`, et dit au démarrage combien
de cartes il voit et quelle journée est ouverte. Pour une autre base :
`py web/app/lancer.py --jeu jeu/jeu_2627.sqlite --saison 2026/27`. La
fenêtre reste occupée tant que le site tourne ; `Ctrl+C` l'arrête.

Puis http://localhost:8000. Le premier compte créé est administrateur. En
démo, les prestations des journées 26 à 34 sont déjà en base : sur
l'écran Admin, « Clôturer la journée » suffit à faire avancer la saison.
Les portraits sont lus dans `moteur/images/joueurs/` (release
`data-2025-26` ou `donnees/portraits.py`) ; sans ce dossier, le marché
affiche des initiales. La fiche d'un joueur (clic sur sa ligne) montre sa
carte dessinée : OVR courant, attributs de la saison, portrait, couleur du
club. Elle est rendue par `/images/cartes/{player_id}.png` et mise en cache
dans `out/cartes_site/` (variable `FL_CACHE`).

Une base neuve pour une vraie saison :

```
py -m jeu.importer --jeu jeu/jeu_2627.sqlite --fotmob moteur/fotmob_2526.db --saison 2025/26
py -m jeu.pipeline journees --saison 2026/27 --jeu jeu/jeu_2627.sqlite --fotmob moteur/fotmob_2627.db
py -m jeu.pipeline amorcer  --saison 2026/27 --jeu jeu/jeu_2627.sqlite --source 2025/26
```

(`amorcer` lit les prestations de la saison source dans la même base,
d'où l'import de 2025/26 d'abord.)

## La semaine type, en vraie saison

1. **Avant le premier coup d'envoi** : rien à faire, la journée se
   verrouille toute seule à l'heure `journee.cloture`.
2. **Après le dernier match de la fenêtre**, sur ta machine, avec ta base
   FotMob à jour :
   ```
   py -m jeu.exporter_journee --saison 2026/27 --journee 3 --jeu jeu/jeu_2627.sqlite --fotmob moteur/fotmob_2627.db
   ```
   Ça écrit `out/journees/2026-27_J3.json` : toutes les prestations notées
   de la fenêtre, avec attributs.
3. Sur le site, écran Admin : **Charger les prestations** (ce fichier),
   puis **Clôturer la journée**. Scores, gains, cartes, prix : tout est
   écrit en une transaction, et relancer ne change rien.

Le serveur n'a donc jamais besoin de la base FotMob ni du cache.

## Mettre en ligne

Le conteneur `Dockerfile` à la racine tient sur n'importe quel hébergeur
qui lance des images Docker avec un volume persistant (Fly.io, Railway,
Render, un petit VPS). Deux choses à fournir : la variable `FL_SECRET`
(une longue phrase, elle signe les sessions) et la base du jeu dans le
volume, `/data/jeu.sqlite`. Les portraits sont dans l'image si
`moteur/images/joueurs/` est rempli au moment du `docker build` (65 Mo),
sinon les cartes affichent des initiales.

Sauvegarde : le fichier `/data/jeu.sqlite` est tout l'état du jeu. Le
copier après chaque clôture suffit.

## API

`/api/docs` donne la liste. Les appels d'écriture demandent le cookie de
session ; ceux sous `/api/admin` demandent un compte administrateur
(`FL_ADMINS=pseudo1,pseudo2` pour en nommer d'autres que le premier).

## Ce que le site ne fait pas encore

- Le verrouillage automatique repose sur l'horloge du serveur et l'heure
  de clôture importée du calendrier ; un match avancé ou reporté demande
  de retoucher `journee.cloture` (écran Admin : verrouiller / rouvrir).
- Pas de récupération de mot de passe : l'administrateur peut le
  réinitialiser en base.
- Pas de notifications.

À la clôture d'une journée, la composition de chaque équipe est
reconduite telle quelle sur la journée suivante (`pipeline.reconduire_compositions`) :
un manager qui oublie de la renvoyer garde son onze, et peut la modifier
jusqu'au verrouillage.

## Design

Une seule ambiance, la nuit de stade : fond bleu nuit, surfaces en verre
sombre, or pour ce qui compte (budget, OVR élevés, capitaine), la couleur
du club sur chaque carte. Tout est dans `web/app/static/style.css`, sans
framework.

La carte du marché est un **écusson** (`clip-path`, variable `--clip`) :
bord biseauté en dégradé, haut aux couleurs du club avec l'OVR, le poste,
l'âge, le drapeau, le numéro et le portrait, bas sombre avec le nom, le
club, la forme récente (six dernières notes), le prix et le bouton. Une
carte possédée a le bord doré. Sur le terrain, les onze sont des
mini-écussons ; la fiche montre la carte dessinée par `jeu/cartes.py`,
qui prend la même silhouette (`cartes.ecusson` prolonge le bandeau du bas
en pointe, avec le liseré du club).

Âge, numéro et nationalité viennent des feuilles de match FotMob, comme
la valeur marchande (`importer.lire_valeurs`). La page d'accueil montre
quatre cartes vitrine (`/api/vitrine`, sans compte). Sur mobile la
navigation passe en barre du bas et le marché en deux colonnes.
