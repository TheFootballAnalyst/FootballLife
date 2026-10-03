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
| Packs | la boutique de la banque : vingt packs (Bronze 25 M€, Argent 60, Or 90, Élite 250 ; mixte ou par ligne), cinq cartes (sept pour l'Élite) avec des garanties lisibles et les chances affichées, ouverture animée, les cartes vont en réserve. Un pack peut tirer une carte qu'on a déjà : c'est un doublon, il ne s'aligne pas, il se vend (banque à 25 % de la cote, ou enchères). Un pack Bronze offert par jour de connexion, un Argent au septième jour d'affilée. Le détail et les raisons : `docs/ECONOMIE.md` |
| Enchères | l'hôtel des ventes : mises à prix, achat immédiat, offres (argent bloqué), fin de vente ; tes ventes et tes offres |
| Lobby | le match classé : ton onze contre celui d'un autre manager, joué avec les cartes sur le terrain du moteur B, un match complet au rythme du football (×2, les arrêts de jeu sautés, une demi-heure), tactique, formation et remplacements en direct ; ton Elo classé et tes derniers matchs |
| Solo | la campagne : tu prends la place d'un vrai club dans une vraie compétition et tu joues son calendrier contre les onze des autres clubs ; crédits et packs selon la place ou le tour atteint |
| Équipe | formation, onze sur le terrain, capitaine, ordre du banc, **tactique de départ** (les trois axes et les consignes aux lignes, valables pour tous tes matchs), **Envoyer la composition** avant le premier coup d'envoi ; **Mon club** : effectif et réserve, aligner, mettre en vente, vendre à la banque |
| Journée | le résultat de la dernière journée (détail par joueur, entrants du banc, rang), l'état de la journée en cours, l'historique |
| Classement | mondial, plus les ligues privées : créer une ligue donne un code, le partager suffit |
| Admin | verrouiller ou rouvrir la journée, charger les prestations notées, clôturer |

Règles appliquées côté serveur : 18 cartes sur la feuille (11 + 7),
réparties comme le manager veut — plus aucun quota par ligne ; la
réserve du club n'a pas de plafond ; onze titulaires, **n'importe qui à n'importe quelle
case** — le poste se paie dans le match, il ne se refuse pas (voir « La
composition ») ; capitaine titulaire ;
composition refusée après la clôture ; marché fermé entre la clôture et
le calcul ; prix = prix OVR × (1 + part des équipes qui possèdent la
carte), recalculé à chaque clôture.

## Lancer chez soi

```
py -m pip install fastapi "uvicorn[standard]" python-multipart
py web/app/demo.py                                   # -> jeu/demo.sqlite : cartes = la saison 25/26 entière,
                                                     # marché ouvert à J26 ; construit d'abord jeu/jeu_2526.sqlite
                                                     # depuis moteur/fotmob_2526.db s'il n'existe pas (4 min en tout)
py web/app/lancer.py                                 # sert http://localhost:8000 sur la base de démo
```

`lancer.py` choisit la base (`jeu/demo.sqlite` si elle existe), génère et
garde un secret de session dans `jeu/.secret`, et dit au démarrage combien
de cartes il voit et quelle journée est ouverte. Il refuse de servir une
base sans carte ; et `demo.py` reconstruit une base du jeu **vide**
(un fichier au bon nom créé par un lancement prématuré) au lieu de la
copier. Sur la base de démo, les packs sont **sans limite
d'exemplaires** : avec dix milliards au premier compte, le plafond de
trois copies par carte épuisait tous les packs en une soirée. `--copies
3` remet la rareté d'une vraie ligue, `FL_PLAFOND_COPIES` fait pareil
pour un serveur lancé autrement (0 = sans limite). Pour une autre base :
`py web/app/lancer.py --jeu jeu/jeu_2627.sqlite --saison 2026/27`. La
fenêtre reste occupée tant que le site tourne ; `Ctrl+C` l'arrête.

Pour essayer les nouveautés sans toucher à ta base : `py
outils/environnements.py creer test` puis `lancer test` (port 8001, sur
une copie `jeu/test.sqlite` ; ta prod reste `py web/app/lancer.py`). Pour
garder à côté un témoin au code figé (le jeu initial d'avant les
chantiers, le miroir de ce qui est en ligne) : `creer initial`, `lancer
initial`. Ce qui est réversible et comment : `docs/ENVIRONNEMENTS.md`.

La base est ouverte en mode WAL avec une attente de quinze secondes sur
le verrou : les lectures (les cartes qui se dessinent par dizaines) ne
bloquent jamais l'écriture (ouvrir un pack, faire un changement). Deux
fichiers `demo.sqlite-wal` et `demo.sqlite-shm` vivent à côté de la base,
c'est normal. **Ne mets pas le projet dans un dossier synchronisé
(OneDrive, Documents sur un PC d'entreprise)** : la synchronisation
tient le fichier et SQLite répond « database is locked ».

Puis http://localhost:8000. Le premier compte créé est administrateur. En
démo, les prestations des journées 26 à 34 sont déjà en base : sur
l'écran Admin, « Clôturer la journée » suffit à faire avancer la saison.

**Sur quoi les cartes de la démo sont amorcées.** Sur la saison 2025/26
**entière**, telle que le moteur la lit — chaque match de la base
FotMob, Coupe du monde comprise, plus le palmarès de la saison — comme
un vrai lancement le ferait avec la saison précédente. La démo amorçait
avant sur les journées 1 à 25 seulement (encore possible : `--amorce
1-25`), et ça coupait le printemps : Dembélé, blessé à l'automne et
injouable à partir de mars, sortait 68e quand le barème du moteur le
donne premier de loin. Amorcé sur la saison entière il est à 98, à
égalité en tête. Les journées 26 à 34 que la démo rejoue ont donc aussi
nourri l'amorce, ce qu'une démo supporte ; une vraie saison ne les voit
jamais deux fois. `--etat 25` fixe la dernière journée considérée jouée.
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

**Le premier compte est le compte de démonstration.** C'est déjà celui
de l'administrateur — c'est lui qui monte la base et qui fait visiter le
jeu — et il démarre avec **10 milliards d'euros** au lieu des 30 M€ (et de
l'effectif tiré au sort) de tout le monde, de quoi acheter n'importe quelle carte sans passer une heure
au mercato. Tous les comptes suivants démarrent normalement.

Une vraie mise en ligne voudra le désactiver : `FL_BUDGET_PREMIER=0` (ou
vide) rend au premier compte le budget de tout le monde, et n'importe
quel autre montant en M€ le fixe à ce montant (`FL_BUDGET_PREMIER=250`).

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

## Le rythme du match

Un match est un match complet de quatre-vingt-dix minutes simulées, joué
au rythme du football : le ballon vivant à ×2, et **les arrêts de jeu
sautés** comme dans le bac (touche, coup franc, corner, célébration :
l'écran ne montre que les deux dernières secondes de chacun). Un match
complet, c'est 52 minutes de ballon vivant et 77 arrêts, donc **une
demi-heure réelle** à ×2. Un match classé entre deux managers se joue à
×2, horloge commune. Contre la machine — défi, campagne — tu choisis le
rythme au coup d'envoi : ×2 (une demi-heure), ×4 (un quart d'heure) ou
×8 (neuf minutes, un résumé). Le choix est mémorisé, la vitesse est
celle de la rencontre (`rencontre.vitesse`), et l'horloge du match est
le match lui-même : la minute affichée est celle que le match a
atteinte, pas une règle de trois sur l'heure (docs/MOTEUR_B.md, « Le
moteur B dans le jeu »). L'ancien moteur A n'est plus dans le direct
(chantier 6) : il ne joue plus que les autres matchs d'une journée de
campagne, ceux qu'on ne regarde pas.

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

## Ce que tu décides pendant le match

**Changements et permutations, un seul geste.** Dans l'onglet Tactique,
deux listes : le terrain et le banc. Un du terrain et un du banc, c'est
un changement. Deux du terrain, c'est une **permutation** : ils
échangent leurs postes — Valverde monte de DD à MC et le relayeur
descend, les deux ailiers changent d'aile — sans compter dans les cinq
changements et sans limite. Tout prend effet à la minute suivante, et
chacun paie (ou gagne) le poste où il se retrouve, comme sur l'écran
Équipe.

**Les coups de pied arrêtés** ont leur tireur, lu dans ton onze et pas
choisi : le meilleur finisseur prend les penaltys, le meilleur créateur
frappe les corners, et ça change tout seul quand il sort. Une faute dans
le dernier tiers est parfois une faute **dans la surface** : il en tombe
0,24 par match, ce que donne le vrai football, et 83 % sont transformés.
À mon premier chiffre il en tombait 0,56 et le score montait de 1,29 à
1,50 but par camp — c'est pour ça qu'on mesure.

**Parle à ton équipe.** En tête du panneau Ajuster, une boîte où tu
écris ce que tu dirais du bord du terrain : « on presse haut », « les
latéraux restent derrière », « Hakimi, reste derrière », « marquez
Mbappé », « Kolo Muani remplace Dembélé », « Hakimi et Mendes
permutent », « on passe en 4-4-2 », et à la pause « réveillez-vous ».
Le coach répond ce qu'il en fait (« Achraf Hakimi et sa ligne : les
latéraux restent derrière. ») et le levier s'applique comme un clic,
avec les mêmes règles et les mêmes refus en clair. Une consigne à un
joueur vaut pour sa ligne, et la réponse le dit ; ce que le moteur ne
sait pas faire est dit aussi, et une phrase incomprise reçoit quatre
exemples pris dans la situation. Des règles et un vocabulaire
(`jeu/dialogue.py`), pas d'intelligence artificielle en ligne : le jeu
marche hors ligne, et une autre langue est une autre table.

**La causerie de mi-temps.** Tu leur parles une fois, et ce que tu dis
ne vaut pas la même chose selon le score : secouer une équipe menée
n'est pas secouer une équipe qui mène. L'effet dure vingt minutes.

| Tu les… | quand tu mènes | quand c'est nul | quand tu es mené |
| --- | --- | --- | --- |
| **secoues** | un peu d'urgence | +percussion, −contrôle | ils répondent le plus fort |
| **rassures** | +contrôle, +défense, −percussion | idem, plus doux | ça ne renverse rien |
| **félicites** | +finition, +création, −défense | presque rien | hors sujet, et ça endort |

**Le marquage.** Tu peux coller un homme sur l'un des leurs. Il pèse
moins — d'autant moins qu'il sort de **son propre onze** — mais celui
qui le suit passe son match à le suivre. Mesuré sur de vrais clubs :
marquer leur meilleur vaut +0,031 but, un joueur moyen −0,068, leur plus
faible −0,068. Ça ne se justifie que contre un vrai danger.

Le niveau se mesure contre leur équipe et non contre le vivier, et c'est
tout le sujet : contre le vivier, dès que les deux camps sont bons, tout
le monde est au-dessus de la moyenne et marquer n'importe qui rapportait.

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

Le match se regarde comme depuis le banc, sur le terrain du moteur B
(`web/app/static/terrain_b.js`, partagé avec le bac) : vingt-deux
**jetons** — bleus pour les tiens, rouges pour eux, le poste dedans, le
nom dessous, le porteur cerclé — un vrai ballon avec son ombre et sa
trajectoire en l'air, des cages dont les filets ondulent quand ça
rentre, le gardien qui ferme l'angle. Ce qui bouge est ce que le moteur
a calculé pas à pas (docs/MOTEUR_B.md, « Le moteur B dans le jeu ») : les
images de positions arrivent du serveur à chaque sondage et le terrain
les joue derrière, à la vitesse de la rencontre, sans jamais inventer
une course. Le ballon vivant se joue en entier, chaque arrêt de jeu se
saute jusqu'à ses deux dernières secondes.

**L'écran suit le terrain, pas le serveur.** Le serveur a quelques
secondes d'avance ; le score, la minute, le fil du direct, le bandeau
d'action et la pop-up d'un but ou d'un rouge ne s'affichent que quand le
terrain a montré l'action — lire le but avant de le voir, c'est le
décalage que tout le monde remarque. Le nom de la phase en cours
(construction, pressing, bloc bas…) est écrit aux deux coins du terrain,
dans la langue de l'écran.

**L'endurance.** Chacun s'use minute après minute, selon la ligne où il
joue et selon la façon dont tu le fais jouer : presser haut et jouer
direct coûtent des jambes, garder le ballon et descendre le bloc en
économisent. Un milieu finit un match normal autour de 45, un gardien
ne se fatigue presque pas. À vide, un joueur vaut 88 % de lui-même —
assez pour que la dernière demi-heure soit une décision, jamais assez
pour transformer une bonne carte en mauvaise. Les barres se lisent sous
chaque joueur sur le terrain, et dans le panneau des changements, les
plus fatigués en tête.

**Le bac à sable du moteur B** (`/bac`) est une autre page : deux clubs
et une graine, le match se joue sur un vrai terrain (jeu/emergent.py :
vingt-deux joueurs qui décident, un ballon qui a sa physique, un but qui
est un ballon qui franchit la ligne) et se rejoue image par image avec
le fil, les statistiques et la course de chacun. Il ne touche à rien
dans le jeu ; il sert à regarder et à calibrer (docs/MOTEUR_B.md).

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

**Les pieds se lisent en jauges, pas en étoiles.** Sur la fiche et sur
chaque carte, deux icônes de pied : le pied fort est plein, le mauvais
pied se remplit selon sa qualité (4/5 : presque plein). Un droitier
dont le mauvais pied est à 5 est simplement ambidextre : deux pieds
pleins. Sans fiche, deux pieds vides en pointillé. La fiche montre
aussi le **physique** (les neuf jauges EA, la taille, le poids) et le
**potentiel** : ce que la carte peut atteindre cette saison, son OVR
de départ plus ce que son âge lui laisse gagner — à 19 ans la marge de
montée vaut 1,4 fois celle d'un joueur de 27 ans, et la marge de
descente 0,7 fois ; à 34 ans c'est l'inverse (jeu/evolution.py,
`DEVELOPPEMENT`). L'âge borne donc l'OVR en saison : les jeunes qui
jouent montent plus haut, les anciens qui glissent descendent plus bas.

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
court est une touche. **N'importe quelle carte peut aller sur n'importe
quelle case**, et deux titulaires qu'on glisse l'un sur l'autre
échangent leurs postes. Ce qui se paie (`scoring.malus_poste`) a deux
parts. La **distance** entre la case et le poste le plus proche que le
joueur a vraiment tenu : 4 pour un cran (central → latéral, relayeur →
pivot), 8 pour deux, 14 pour trois, 30 entre les buts et le champ, 2
pour la mauvaise aile. Et **ses attributs** : chaque poste pèse les six
axes à sa façon (`scoring.POIDS_POSTE`, la finition d'un buteur, la
défense d'un central), et hors de son poste une carte paie la moitié de
la distance moins ce que ses attributs valent de plus au nouveau poste
qu'au sien. Raphinha, avec sa finition, joue buteur pour rien ; un
central en pointe paie la distance et sa finition. Quand les attributs
l'emportent, c'est un **bonus**, au plus +3, rare et mérité. La case le
dit — orange pour un peu, rouge pour loin de chez lui, vert pour un
bonus — avec **l'OVR qu'il vaut à ce poste**, et l'écran donne l'OVR
moyen du onze au poste.

**D'où vient le poste d'une carte.** Des feuilles de match FotMob : la
case que le joueur occupait dans le onze, lue par le moteur match par
match (un couloir bas d'une défense à quatre est un latéral, le côté
d'un milieu à quatre est un ailier, l'axe le plus bas du milieu est le
6…). Le poste principal est celui où il a passé le plus de minutes,
et la carte est éligible partout où il a joué un cinquième de son
temps. Quand cette lecture se trompe sur quelqu'un — Valverde sort
ailier parce que le Real l'aligne à droite d'un milieu à quatre —
c'est `moteur/postes_manuel.json` qui tranche, le même fichier que le
moteur utilise pour son propre classement : `{"Federico Valverde":
"Milieu relayeur"}`, puis `py -m jeu.importer --postes-seulement --jeu
jeu/demo.sqlite` (et sur `jeu/jeu_2526.sqlite`) pour l'appliquer sans
tout réimporter. Le poste imposé passe devant, les autres qu'il a tenus
restent jouables.

**MG et MD.** Le côté d'un milieu à quatre (la case FotMob de la ligne
7, en couloir, devant une défense à quatre) n'est pas une aile : le
moteur le note comme un ailier, le jeu le nomme comme FIFA, milieu
gauche ou milieu droit. Le 4-4-2, le 4-5-1, le 4-1-4-1 et le 5-4-1
s'écrivent donc MG · … · MD ; les 4-3-3 et le 4-2-3-1 gardent leurs
ailiers. MG/MD est à un cran du latéral, du relayeur et de l'ailier,
et les consignes aux ailiers le concernent. Sur une base déjà
construite : `py -m jeu.importer --postes-seulement --jeu
jeu/demo.sqlite --fotmob moteur/fotmob_2526.db` relit les prestations
depuis les cases FotMob ; 1246 prestations et 168 joueurs y passent en
2025/26 (Pépé, Giuliano Simeone, Baena…). Le fichier versionné
`jeu/postes_manuel.json` complète celui du moteur et impose, lui,
Valverde en MC — sa carte est MC, jouable MD et DD.

**Le côté d'un joueur de couloir vient de la fiche EA.** Le moteur lit
« latéral » ou « ailier » sans côté, si bien qu'Hakimi pouvait se
retrouver DG et Yamal AG. `moteur/physique_ea.csv` (la fiche EA Sports,
jointe par identifiant FotMob) dit RB, LB, RW, LW, RM, LM : la carte
devient DD, DG, AD, AG, MD ou MG, et le malus de côté (2 points) joue
quand tu l'alignes du mauvais côté. Un joueur dont le poste EA est
axial garde ses couloirs sans côté — on ne devine pas. Le poste
principal du barème ne change pas ; seule la liste des postes tenus
porte le côté. Sur une base déjà construite : `py -m jeu.importer
--physique-seulement --jeu jeu/demo.sqlite` (et `demo.py` le fait tout
seul quand la base ne l'a pas encore).

La fiche est en deux passes qui se lisent à la suite,
`moteur/physique_ea.csv` puis `moteur/physique_complement.csv` (le
complément, apparié sur les noms d'usage, n'a ni date de naissance ni
poste EA : ses joueurs n'ont donc ni côté ni date, Vinícius reste AG/AD
tant qu'on ne lui met pas un poste). Un joueur sans fiche reçoit le **profil médian de son poste**,
calculé sur les vraies fiches de la base et signalé comme tel sur sa
fiche : un ailier inconnu accélère comme un ailier, pas comme un 50
partout. Et pour 583 joueurs, la fiche montre ce que FotMob a
**réellement mesuré en Ligue des champions** (pointe en km/h, distance
et sprints par 90 minutes, `moteur/mesures_fotmob_ucl.json`) — la
règle de conversion mesurée, dix points de note EA pour 1,41 km/h,
servira au moteur émergent. Les scripts d'appariement et l'état des
lieux sont dans `donnees/physique/`.

La même fiche donne **le pied fort et la qualité du mauvais pied** (1 à
5), **la date de naissance** — l'âge est calculé à la date où en est la
base, pas au jour de l'import — et **le profil physique** :
accélération, vitesse de pointe, agilité, équilibre, réactions,
endurance, force, détente, agressivité, taille, poids, gestes
techniques. La fiche est une extraction du jeu de données EA FC 26
**figée au 16 septembre 2026** : on ne ré-extrait pas en cours de
saison, les notes EA bougent chaque semaine et la valeur des cartes
bougerait sans raison de jeu. Chaque fiche porte l'orientation de sa
colonne « pied fort » dans `importer.FICHES_PHYSIQUE` (une première
extraction l'avait à l'envers ; celles du 16 septembre sont à
l'endroit, vérifié sur dix témoins). Les homonymes et les identifiants
EA partagés sont réglés à la source par `nettoie_complement.py`
(club, poste puis patronyme) ; `moteur/physique_exclus.json` reste
comme filet, vide.

Les postes s'écrivent comme dans FIFA — GB, DC, DG, DD, MDC, MC, MOC,
MG, MD, AG, AD, BU — partout : sur les cases, dans la ligne de chaque joueur du
club et des listes (ses postes tenus en premier), sur la fiche. Cinq
4-3-3 se distinguent par leur milieu : (1) MC · MDC · MC, (2) MC · MC ·
MC, (3) MC · MOC · MC, (4) MDC · MDC · MC, (5) MDC · MC · MOC. Le bouton « meilleur onze » prend, case par
case, la carte qui vaut le plus *là* ; côté moteur, un onze de club ou
un changement de formation résolvent la même question par une vraie
affectation (hongroise) plutôt que case par case, ce qui évite la chaîne
de trois joueurs chacun d'un cran à côté.

Les postes de côté portent leur côté — latéral gauche, ailier droit —
et le milieu d'un 4-3-3 est un pivot derrière deux relayeurs, dessiné en
triangle. Trois milieux axiaux dans ces trois cases ne coûtent qu'un
cran au relayeur qui joue pivot.

Un champ de recherche au-dessus du banc filtre le banc et le club par
nom et allume la carte sur le terrain ; « Mon club » se filtre aussi par
poste tenu (GB, DC, DG… en codes) et se trie par OVR, évolution depuis
le début de saison, cote, prix d'achat, plus-value ou nom.

Le rangement est enregistré case par case : il revient tel que tu l'as
laissé au rechargement.

## Ce que le site ne fait pas encore

- Le verrouillage automatique repose sur l'horloge du serveur et l'heure
  de clôture importée du calendrier ; un match avancé ou reporté demande
  de retoucher `journee.cloture` (écran Admin : verrouiller / rouvrir).
- Pas de récupération de mot de passe (le jeu ne garde qu'une empreinte
  salée) : on en pose un nouveau depuis la machine du serveur,
  `py web/app/mdp.py MANO` (il est demandé au clavier ;
  `--mot-de-passe` pour le passer directement, `--liste` pour voir les
  comptes, `--jeu` pour une autre base que celle de `lancer.py`).
- Pas de notifications.

À la clôture d'une journée, la composition de chaque équipe est
reconduite telle quelle sur la journée suivante (`pipeline.reconduire_compositions`) :
un manager qui oublie de la renvoyer garde son onze, et peut la modifier
jusqu'au verrouillage.

## La coupe entre amis

Dans une ligue privée (écran Classement), une **coupe de la semaine** :
un tableau à élimination directe entre les membres, huit au plus, les
plus forts têtes de série (par Elo classé), les places vides sont des
exemptions ; trois tours à huit, un pack Or au vainqueur, une coupe par
semaine et par ligue. N'importe quel membre la lance.

Chaque match se joue **comme un défi, par le premier des deux qui
clique** : il joue en direct dans le lobby, avec sa tactique et ses
changements ; l'autre est représenté par son onze enregistré (sa
composition de la journée, sa tactique de club), mené par la machine,
sous le nom de son club. L'autre voit le résultat dans le tableau. Un
membre sans onze enregistré perd par forfait ; un nul se décide aux tirs
au but. Rien n'est classé (pas d'Elo), la prime est celle d'un défi.
Le tableau et le bouton « Jouer mon match » sont sous le classement de
la ligue ; les limites du gratuit (`--limites`) comptent ces matchs
comme des défis.

## Les comptes en ligne, le monde fictif

La version en ligne se lance avec les limites du gratuit et le premium
(`lancer.py --limites`, `docs/EN_LIGNE.md` : comptes, mot de passe
oublié, mineurs, paiement par Stripe, sauvegardes) et dans le monde fictif
(`lancer.py --fictif`, `docs/MODS.md` : noms générés, clubs par ville,
avatars dessinés, mods). Le jeu local garde les vrais noms et aucune
limite.

## Les langues

Le site se joue en français ou en anglais (le sélecteur dans la barre ;
sans choix, la langue du navigateur). Tout ce que l'écran dit passe par
un dictionnaire par langue (`static/lang/<code>.json`), le serveur parle
en codes et l'écran traduit — les erreurs, le commentaire du match, le
style d'un onze, les objectifs. La boîte de dialogue comprend l'anglais
(« press high », « Hakimi, stay back », « bring on Kolo Muani for
Dembélé »). Ajouter une langue est un fichier et une table, pas du code :
`docs/LANGUES.md`.

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


## Le maillot du club et les trois globaux d'une carte

Dans l'écran Équipe, sous la tactique de départ, le manager choisit le
maillot de son club : une couleur, une seconde couleur, un motif (uni,
bande centrale, rayures, cerclé, deux moitiés, écharpe), avec un aperçu
en chemise ; enregistré dès qu'on le touche (`POST /api/equipe/maillot`,
colonne `equipe.maillot`). Les clubs réels ont le leur dans
`jeu/maillots.py`.

Chaque carte porte, dans la pointe de l'écusson et sur sa fiche, trois
globaux à côté de l'OVR : PHY (la moyenne du profil physique EA :
accélération, pointe, endurance, force, détente), OFF et DEF (les taux
de travail offensif et défensif : Bas, Moyen, Haut). Les work rates
viennent de la fiche EA quand elle les a ; sinon des trois leviers
mesurés (`moteur/travail_sans_ballon.csv`, rangs dans le poste),
combinés comme le moteur le fait : défensif = 0,6 pressing + 0,4 volume,
offensif = 0,6 volume + 0,4 de ce que disent création et dribble ; haut
à 0,6 et plus, bas à 0,35 et moins. L'infobulle de la fiche donne la
source et les trois leviers sur 9 — `jeu/scoring.contributions`, champ
`globaux` de `/api/cartes`.
