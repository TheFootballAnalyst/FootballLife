# Le site — phase 3

`web/app/` : un serveur FastAPI, une base SQLite (celle de `jeu/schema.sql`),
une page HTML avec son JavaScript. Pas de compilation, pas de framework
côté navigateur. Le serveur ne calcule jamais de note : la clôture d'une
journée est `jeu/pipeline.py`, déclenchée depuis l'écran Admin.

## Écrans

| écran | ce qu'on y fait |
|---|---|
| Connexion | créer un compte (pseudo, mot de passe, nom d'équipe) ; le premier compte est administrateur |
| Cartes | toutes les cartes (écussons ou liste), filtres par poste, ligue, tri (OVR, prix, OVR par M€, forme, âge, popularité), fiche joueur, et le nombre de ventes en cours par joueur |
| Packs | la boutique de la banque : quinze packs (trois niveaux, mixte ou par poste), ouverture animée, les cartes vont en réserve |
| Enchères | l'hôtel des ventes : mises à prix, achat immédiat, offres (argent bloqué), fin de vente ; tes ventes et tes offres |
| Lobby | le match classé : ton onze contre celui d'un autre manager, joué avec les cartes, quatre minutes pour quatre-vingt-dix, tactiques ajustables en direct ; ton Elo classé et tes derniers matchs |
| Solo | la campagne : tu prends la place d'un vrai club dans une vraie compétition et tu joues son calendrier contre les onze des autres clubs ; crédits et packs selon la place ou le tour atteint |
| Équipe | formation, onze sur le terrain, capitaine, ordre du banc, **Envoyer la composition** avant le premier coup d'envoi ; **Mon club** : effectif et réserve, aligner, mettre en vente, vendre à la banque |
| Journée | le résultat de la dernière journée (détail par joueur, entrants du banc, rang), l'état de la journée en cours, l'historique |
| Classement | mondial, plus les ligues privées : créer une ligue donne un code, le partager suffit |
| Admin | verrouiller ou rouvrir la journée, charger les prestations notées, clôturer |

Règles appliquées côté serveur : 18 cartes sur la feuille (11 + 7), au
plus 3 gardiens, 7 défenseurs, 7 milieux, 5 attaquants — les quotas
dépassent volontairement dix-huit, ils sont là pour empêcher une équipe
de huit attaquants, pas pour dicter sa forme ; la réserve du club n'a
plus de plafond ; onze légal (1 gardien, 3 à 5
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
py -m jeu.pipeline amorcer  --saison 2026/27 --jeu jeu/jeu_2627.sqlite --source 2025/26 --fotmob moteur/fotmob_2526.db
```

(`amorcer` lit la saison source dans la base FotMob de cette saison :
le barème de saison de chaque joueur et son palmarès (`moteur/bareme_manuel.json`
à côté), c'est le Ballon d'or maison qui fixe les cartes. Sans base FotMob
il additionne les fenêtres `bareme_journee` de la saison source déjà dans
la base du jeu — terrain seul, sans palmarès. Compter 1 min 30.)

## La semaine type, en vraie saison

1. **Avant le premier coup d'envoi** : rien à faire, la journée se
   verrouille toute seule à l'heure `journee.cloture`.
2. **Après le dernier match de la fenêtre**, sur ta machine, avec ta base
   FotMob à jour :
   ```
   py -m jeu.exporter_journee --saison 2026/27 --journee 3 --jeu jeu/jeu_2627.sqlite --fotmob moteur/fotmob_2627.db
   ```
   Ça écrit `out/journees/2026-27_J3.json` : toutes les prestations notées
   de la fenêtre, avec attributs, et la fenêtre de barème de saison de
   chaque joueur (ce qui fait bouger les cartes ; compter une minute de
   calcul en plus).
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

## Le lobby classé

L'écran Lobby joue un match avec tes **cartes**, pas avec les actions
réelles de la journée. Tu y arrives avec le onze posé sur l'écran Équipe,
tu choisis un tempo, une hauteur de bloc et un niveau de risque, puis tu
cherches un adversaire. Quatre minutes réelles pour quatre-vingt-dix, le
fil se remplit pendant que tu regardes, et tu peux changer tes réglages en
cours de route : le changement prend effet à la minute suivante, jamais
sur ce qui est déjà joué.

Les trois réglages forment un cycle — garder le ballon bat un bloc bas,
un bloc bas bat le jeu direct, le jeu direct bat un bloc haut, un bloc
haut bat la possession — donc aucun n'est le bon choix par défaut.

Si personne n'attend, le bouton « défi » te fait jouer tout de suite
contre un onze assemblé à ton niveau. Un défi ne touche pas ton Elo
classé : le classement n'enregistre que ce qui s'est joué contre
quelqu'un.

## Le mode solo

Tu choisis une compétition — les cinq championnats ou la Ligue des
champions — puis **le club dont tu prends la place**. Tu joues son
calendrier avec ton onze, contre les vrais clubs : leur équipe est bâtie
sur les cartes de leurs joueurs, donc elle vaut ce qu'ils valent cette
saison. Quand Hakimi baisse, le PSG que tu affrontes baisse avec lui.

Un championnat se joue en aller-retour. Les autres matchs de la journée
sont joués eux aussi, donc le classement est un vrai classement, et c'est
la place finale qui paie. Une coupe est un tableau à seize, à élimination
directe, tête de série par la valeur de l'effectif ; un nul se décide aux
tirs au but, et la récompense dépend du tour où tu sors.

Les récompenses sont des crédits (M€) et des **packs offerts**, qui
s'ouvrent depuis l'écran Packs sans rien coûter — ils tirent dans le même
vivier que les autres. Chaque victoire rapporte en plus une petite prime,
pour qu'aucun match ne soit pour rien. Abandonner ne rapporte rien.

Chaque adversaire joue à sa façon, lue sur son propre onze : un club qui
contrôle bien plus qu'il ne finit garde le ballon, un autre joue direct,
une défense faible s'assoit bas. Ce n'est pas tiré au sort — la même
équipe joue toujours pareil — et les seuils sont les terciles des 96
onze des cinq championnats, sinon tout le monde jouait direct et offensif
en même temps.

Tout est rejouable : la graine de la campagne fixe celle de chaque match,
et un résultat est écrit dès qu'il est calculé.

## La composition

Le onze se range en glissant une carte sur une case, ou en la touchant
puis en touchant sa destination — c'est le même geste, un glissé trop
court est une touche. Une carte ne peut aller que sur une case d'un poste
que le joueur a vraiment tenu : Valverde peut jouer ailier, latéral ou
milieu, un gardien ne peut aller nulle part ailleurs. Le joueur délogé
prend la place laissée libre s'il peut y jouer, sinon il part sur le banc
et la case reste vide, en rouge, jusqu'à ce que tu la combles.

Le rangement est enregistré case par case : il revient tel que tu l'as
laissé au rechargement.

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
