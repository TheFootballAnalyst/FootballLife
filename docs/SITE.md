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
| Lobby | le match classé : ton onze contre celui d'un autre manager, joué avec les cartes sur un terrain 2D où elles jouent vraiment les actions, six minutes pour quatre-vingt-dix, tactique, formation et remplacements en direct ; ton Elo classé et tes derniers matchs |
| Solo | la campagne : tu prends la place d'un vrai club dans une vraie compétition et tu joues son calendrier contre les onze des autres clubs ; crédits et packs selon la place ou le tour atteint |
| Équipe | formation, onze sur le terrain, capitaine, ordre du banc, **tactique de départ** (les trois axes et les consignes aux lignes, valables pour tous tes matchs), **Envoyer la composition** avant le premier coup d'envoi ; **Mon club** : effectif et réserve, aligner, mettre en vente, vendre à la banque |
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

## L'écran de match

Quand un match tourne, il **prend l'écran**. Le score et l'horloge en
haut, le terrain au centre, **les deux compositions de chaque côté** —
poste, nom, ce qu'il a fait, son endurance, sa note — et en dessous
trois onglets : **Le direct** (le fil des actions), **Tactique** (les
axes, la formation, les consignes, les changements) et **Statistiques**.
L'onglet reste où tu l'as laissé d'un sondage à l'autre.

**Chaque joueur a une note de match**, comme on en lit sur une feuille
de match. Elle se construit de ce que la simulation a produit : ses buts
et ses passes décisives, ses tirs, ses arrêts, ses fautes et ses
cartons, les buts encaissés s'il défend, et son implication — le nombre
de ballons qu'il a touchés comparé à la médiane de son équipe, parce
qu'un milieu en touche plus qu'un buteur par nature. La base est à 6,6
et non à 6 : sur une échelle de football, 6 n'est pas la moyenne, c'est
un mauvais match. Mesuré sur soixante matchs, la médiane tombe à 6,6, un
buteur autour de 7,8, et 7 % des notes passent 8.

Cette note-là n'a **rien à voir** avec celle du moteur, qui note un vrai
match d'un vrai joueur et qui, elle, fait la carte. Celle du match
simulé vit et meurt avec lui : elle ne remonte jamais vers la carte.

Les **statistiques avancées** : possession, tirs, xG, xG par tir,
corners, fautes, hors-jeu, cartons — et deux dessins. La **course au
xG**, qui distingue une domination d'un cambriolage, et la **carte des
tirs** : chaque frappe à l'endroit d'où elle est partie, grosse comme
son xG, pleine si elle est rentrée.

## Lire l'adversaire

Tu ne vois **pas** la feuille de réglages de l'autre manager. Le cycle
tactique n'est un choix que s'il faut deviner : lire « bloc haut,
offensif » en clair transformerait une lecture de jeu en consultation de
tableau.

À la place, ce qu'un entraîneur voit depuis sa surface technique, déduit
du match et pas des réglages — donc parfois faux, comme une vraie
lecture. Mesuré sur quatre-vingts matchs par réglage, voici ce qui se
lit et ce qui ne se lit pas :

| ce que fait l'adversaire | tirs total | ses tirs | sa possession | ses fautes |
| --- | --- | --- | --- | --- |
| il garde le ballon | 19,1 | 9,2 | **57 %** | 9,5 |
| il joue direct | 27,3 | 14,2 | **42 %** | 13,0 |
| il est offensif | **28,0** | 14,0 | 49 % | 10,5 |
| il est prudent | **19,5** | 9,8 | 49 % | 11,9 |
| bloc haut | 23,0 | 12,8 | 49 % | 11,9 |
| bloc bas | 23,4 | 10,4 | 49 % | 10,8 |
| (neutre) | 22,9 | 11,5 | 49 % | 11,4 |

La possession trahit le tempo, le nombre total de tirs dit si le match
est ouvert, les fautes trahissent un peu le jeu direct. **Le bloc, lui,
ne se lit pas** : haut et bas donnent la même possession et presque les
mêmes tirs. C'est cohérent — le moteur ne modélise pas non plus
l'endroit où le ballon est récupéré — et c'est tant mieux, il reste
quelque chose à deviner. Le jeu ne l'invente donc pas.

Avant la quinzième minute, il n'y a rien à lire et il te le dit.

**La mi-temps** arrête un match à un seul humain, une fois, à la 45e :
le moment où l'on corrige ce qu'on a vu. Un match classé entre deux
managers n'en a pas — ils ne peuvent pas se mettre d'accord pour
souffler.

## Le terrain

Le match se regarde, action par action. Les vingt-deux cartes sont
posées dans leur formation sur un terrain 2D — **les tiennes cerclées de
bleu, celles d'en face de rouge**, le porteur du ballon en doré — et
chaque minute se joue vraiment : la relance du gardien, les passes qui
montent, la conduite dans la surface, **la frappe qui part du pied vers
un point du but**, l'arrêt, le ballon qui file à côté, la perte de
balle, le coup de sifflet sur une faute — les vingt-deux s'arrêtent et
attendent la reprise. L'événement s'annonce au moment où il arrive :
but, arrêt, occasion manquée, corner, faute, carton, hors-jeu, blessure,
remplacement, changement de formation.

**Les onze bougent, pas deux blocs.** Pendant chaque phase, chacun se
déplace selon son poste : le latéral déborde, l'ailier tient la largeur
ou rentre, le milieu se projette, les centraux se resserrent sans jamais
se marcher dessus, et sur une frappe les attaquants rentrent dans la
surface pendant que la défense adverse couvre son but. Les consignes du
manager changent ces courses.

Rien n'est inventé par la page : le moteur rend `fil`, une ligne par
minute (quel camp a le ballon, dans quelle zone, quel joueur le porte,
quel événement) et, dans chaque ligne, `s` — **les phases** de cette
minute. Elles tirent leur propre dé, séparé de celui du match : ajouter
une passe au dessin ne déplace jamais un but. L'horloge reste celle du
serveur.

**L'endurance.** Chacun s'use minute après minute, selon la ligne où il
joue et selon la façon dont tu le fais jouer : presser haut et jouer
direct coûtent des jambes, garder le ballon et descendre le bloc en
économisent. Un milieu finit un match normal autour de 45, un gardien
ne se fatigue presque pas. À vide, un joueur vaut 88 % de lui-même —
assez pour que la dernière demi-heure soit une décision, jamais assez
pour transformer une bonne carte en mauvaise. Les barres se lisent sous
chaque joueur sur le terrain, et dans le panneau des changements, les
plus fatigués en tête.

## Diriger le match

**Six minutes réelles pour les quatre-vingt-dix.** Un match à un seul
humain — un défi, une campagne solo — se **met en pause** : le
classement, lui, ne s'arrête pas, deux managers ne tiennent pas la même
horloge.

**Chaque joueur a un profil, et il n'est pas étiqueté à la main.**
Vitinha s'épanouit dans une équipe qui garde le ballon ; Nuno Mendes est
mal à l'aise si tu lui demandes de rester derrière. Le jeu ne le décide
nulle part : il le **lit** dans la carte, qui vient elle-même de ce que
le joueur a vraiment fait sur un terrain.

Le profil est lu deux fois de suite, et les deux comptent :

- **contre sa ligne.** Un central défend mieux qu'un attaquant ; sans ça,
  tout défenseur passerait pour un amoureux du bloc bas. Ce qui compte,
  c'est un latéral qui progresse plus que *les autres latéraux*.
- **contre lui-même.** Sinon un joueur élite, au-dessus de la médiane
  partout, serait à l'aise dans toutes les tactiques à la fois, et le
  profil deviendrait un cadeau aux gros effectifs. Le profil mesure donc
  une **forme**, pas un niveau : il fait zéro en moyenne. Un joueur
  complet n'a de profil nulle part — et c'est une information sur lui.

Une tactique qui lui va le fait jouer jusqu'à **10 % au-dessus de
lui-même** — environ trois points de carte sur un attribut à 70, un
tiers du malus de hors-poste. Une qui le dessert, autant en dessous.
Mesuré sur quatorze onzes de vrais clubs, le même réglage joué avec et
sans : le bon choix vaut +0,107 but par match, le mauvais −0,071, soit
0,18 but d'écart.

Ce qu'un **onze entier** peut y gagner est plafonné à 2 %, et c'est une
garantie plus qu'un correctif : à tactiques identiques des deux côtés,
l'aise déplace le football de 1,96 à 1,98 but par camp, autant dire
rien. Le plafond assure qu'aucun effectif taillé exprès ne transformera
une bonne lecture en avantage collectif — la lecture se paie en choix,
jamais en niveau offert. Une tactique qui dessert son équipe, elle,
garde son coût entier : bien lire rapporte peu, mal lire coûte cher.

Tu lis tout ça sur **la fiche d'un joueur** — où il est chez lui, où il
l'est moins, et ce que ta propre tactique lui fait — et sur l'écran
Équipe, qui te dit ce que ton réglage fait à ton onze : *« +3,6 % en
moyenne · elle sert Olise +10 %, Szoboszlai +10 % · elle dessert
Konaté −5 % »*.

**Ta tactique de départ se règle une fois.** Comme la composition, elle
vit sur l'écran Équipe : les trois axes et les cinq consignes, enregistrés
sur ton club dès que tu y touches. Tous tes matchs — classés, défis,
campagnes solo — commencent dans cette configuration, et tu la retrouves
sur l'écran Lobby avant le coup d'envoi. Contrairement à la composition
elle n'est jamais verrouillée par la journée : les matchs du lobby se
jouent n'importe quand. Ce que tu changes en direct pendant un match ne
la touche pas — la prochaine rencontre repart de ton réglage.

**Les consignes aux lignes.** En plus des trois axes, tu dis à chaque
ligne ce que tu attends d'elle, et chaque consigne est un échange,
jamais un bonus — le premier choix de chaque ligne ne touche à rien.

| Ligne | Consignes |
| --- | --- |
| Latéraux | monte dans son couloir · **reste derrière** (+défense, −percussion) · **rentre dans l'axe** (+contrôle, −défense) |
| Ailiers | équilibré · **colle la ligne** (+percussion, −création) · **repique dans l'axe** (+création, +finition, −percussion) |
| Milieux | équilibré · **rejoint l'attaque** (+percussion, −défense) · **reste derrière** (+défense, +contrôle, −percussion) · **organise sur les côtés** (+création, −contrôle) |
| Attaquants | équilibré · **cherche la profondeur** (+percussion, −création) · **joue en pivot** (+contrôle, +création, −percussion) |
| Relance | équilibrée · **courte, par le bas** (+contrôle, −défense) · **jeu long** (+percussion, +défense, −contrôle) |

Mesuré sur sept cents matchs par consigne, aucune ne vaut plus d'un
vingtième de but à celui qui la donne : ce que tu gagnes d'un côté, tu
le paies de l'autre. Cinq consignes qui vont toutes dans le même sens ne
font pas non plus une équipe deux fois meilleure sur un trait — le
produit est borné. Elles se voient aussi **sur le terrain** : un latéral
à qui tu demandes de rester derrière ne monte plus (son amplitude passe
de 31 % du terrain à 16 %), un ailier qui repique quitte le couloir.

Les clubs que fait jouer la machine en ont aussi, lues dans leur propre
onze : une équipe qui garde le ballon ressort par le bas et joue en
pivot, une équipe directe joue long et cherche la profondeur.

**La tactique** se change en direct (tempo, bloc, risque) et **la
formation avec** : les dix formations sont là. Le onze reste sur le
terrain, on le redistribue sur les postes de la nouvelle forme comme le
fait le bouton « meilleur onze » — le latéral droit d'un 4-3-3 devient
piston dans un 3-5-2 s'il a déjà tenu le poste — et qui se retrouve hors
de son poste perd dix points sur chaque attribut.

Tu as **cinq remplacements en trois arrêts de jeu**, comme le règlement.
Ils sont horodatés par la même horloge que les changements tactiques :
ils ne touchent jamais ce qui est déjà joué. Un entrant peut ressortir,
un expulsé ne rentre pas, et **l'entrant prend le poste de celui qu'il
remplace**. Les remplaçants sont ceux que tu as nommés sur l'écran
Équipe.

**Une blessure arrête le match.** Le moteur ne remplace plus à ta place :
il sort le blessé, l'arbitre arrête l'horloge et l'écran te demande qui
entre. Un seul coup de sifflet par blessure — si tu repars sans changer,
tu joues à dix, et c'est ton choix. Les clubs que fait jouer la machine,
eux, remplacent tout seuls.

## Le mode solo

Tu choisis une compétition — les huit championnats, la Ligue des
champions, la Ligue Europa ou la Conference League — puis **le club dont
tu prends la place**. Tu joues **son**
calendrier, le vrai, lu dans la base : les huit adversaires qu'un club a
réellement tirés en phase de ligue, l'ordre réel d'une saison de
championnat. Les adversaires sont les vrais clubs, alignés avec les
cartes de leurs joueurs, donc ils valent ce qu'ils valent cette saison.
Quand Hakimi baisse, le PSG que tu affrontes baisse avec lui. Tout suit
la saison de la base : importe 2026/27 et la campagne se joue en
2026/27.

Un **championnat** se joue en aller-retour. Les autres matchs de la
journée sont joués eux aussi, donc le classement est un vrai classement,
et c'est la place finale qui paie.

La **Ligue des champions** est au format réel depuis 2024 :

- une phase de ligue à 36, chacun contre huit adversaires différents, un
  seul classement ;
- les 8 premiers vont directement en huitièmes ;
- du 9ᵉ au 24ᵉ, barrages en aller-retour (les 9-16 reçoivent au retour) ;
- du 25ᵉ au 36ᵉ, éliminés ;
- huitièmes, quarts et demies en aller-retour, finale sur un match.

Une double confrontation se joue au cumul des deux manches, et un cumul à
égalité se décide aux tirs au but — plus de but à l'extérieur, comme
l'UEFA depuis 2021.

Le champ européen est de trente-six. Une base qui ne couvre pas tous les
championnats n'a de cartes que pour une partie des clubs qui se
sont vraiment qualifiés — les autres jouent dans des championnats qu'elle
n'a jamais importés — et un tableau bâti sur vingt n'est pas la
compétition. Le champ est donc complété par les clubs les plus forts dont
le jeu A des cartes : le format est le vrai, et chaque club dedans est un
vrai club avec de vraies cartes. Le calendrier réel n'est utilisé que
s'il couvre tout le champ ; sinon le tirage est engendré, parce qu'une
demi-phase de ligue avec des clubs à deux matchs et d'autres à neuf est
plus loin de la compétition qu'un tirage complet.

Les récompenses sont des crédits (M€) et des **packs offerts**, qui
s'ouvrent depuis l'écran Packs sans rien coûter — ils tirent dans le même
vivier que les autres. Chaque victoire rapporte en plus une petite prime,
pour qu'aucun match ne soit pour rien. Abandonner ne rapporte rien.

Chaque adversaire joue à sa façon, lue sur son propre onze : un club qui
contrôle bien plus qu'il ne finit garde le ballon, un autre joue direct,
une défense faible s'assoit bas. Ce n'est pas tiré au sort — la même
équipe joue toujours pareil — et les seuils sont les terciles des 96
onze des huit championnats, sinon tout le monde jouait direct et offensif
en même temps. Les clubs tenus par la machine font aussi leurs
changements.

**Ton match se joue en direct**, sur le même terrain et la même horloge
qu'un match de lobby : tu le regardes, tu ajustes, tu fais tes
changements. Les autres matchs de la journée sont joués à la clôture,
quand les quatre-vingt-dix minutes du tien sont écoulées. Techniquement
c'est une rencontre ordinaire rattachée à la campagne — il n'y a qu'un
seul mécanisme de match en direct dans le jeu, pas deux.

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
