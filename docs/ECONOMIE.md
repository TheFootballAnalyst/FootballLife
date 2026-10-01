# Économie, droits, mise en ligne : état des lieux et propositions

Ce document répond à cinq questions : comment équilibrer les points de
départ et les gains ; ce que vaut un pack en argent réel ; combien de
cartes par pack ; comment garder des cartes de joueurs sans les droits ;
et comment passer en ligne (gratuit limité, premium). Les chiffres de
l'état des lieux sont lus dans la base de démo (2 371 cartes, saison
2025/26) et dans le code (`jeu/marche.py`, `jeu/evolution.py`,
`jeu/solo.py`). Les propositions sont des propositions : rien n'est
encore changé dans le code.

## 1. L'état des lieux

**La monnaie.** Le jeu compte en millions d'euros fictifs (M€). Une
carte a une **cote**, son prix de référence, qui double tous les +8 OVR
depuis le début de saison (`PRIX_DOUBLE_TOUS_LES`) et ne descend pas
sous 0,1 M€. Sur la base de démo :

| OVR | cartes | cote médiane |
|---|---|---|
| moins de 60 | 1 117 | 4,3 M€ |
| 60–64 | 397 | 6,0 |
| 65–69 | 334 | 8,5 |
| 70–74 | 252 | 13,8 |
| 75–79 | 156 | 20,2 |
| 80–84 | 74 | 44,4 |
| 85–89 | 28 | 69,7 |
| 90 et plus | 13 | 107,9 |

Un 80 vaut 33 M€, un 85 68 M€. Les quinze meilleures cartes du jeu
valent 1 867 M€ à elles seules.

**Le départ.** 100 M€ (`BUDGET_INITIAL`) pour un effectif de 18 cartes :
5,6 M€ par carte, soit un onze de départ autour de **56 d'OVR**. Le
premier compte créé (la démo) reçoit 10 000 M€.

**Les packs** (`PACKS`), tirage uniforme parmi les cartes du palier
encore sous le plafond de copies, +20 % pour un pack d'un poste :

| pack | prix | contenu | valeur attendue des cartes (cote) | ratio | revente banque (40 %) |
|---|---|---|---|---|---|
| Bronze | 6 M€ | 3 cartes < 60 (OVR médian 52) | 24,4 M€ | 4,07 | **9,8 M€ : +63 %** |
| Argent | 25 | 3 cartes 60–74 (66) | 42,6 | 1,70 | 17,0 : −32 % |
| Or | 50 | 1 carte ≥ 75 (79) + 2 cartes 60–74 | 67,3 | 1,35 | 26,9 : −46 % |
| Ultra | 200 | 10 cartes : 3 ≥ 80 (83) + 7 ≥ 75 (79) | 444,0 | 2,22 | 177,6 : −11 % |

Le pack Bronze rapporte plus revendu à la banque qu'il ne coûte : un
joueur qui a compris ça a un budget infini. C'est le premier défaut à
corriger, avant tout réglage fin. L'Ultra est aussi deux fois trop
généreux par rapport aux packs Argent et Or.

**Les gains.**
- Campagne solo : 1,5 M€ par victoire, 0,5 par nul (`PRIME_VICTOIRE`,
  `PRIME_NUL`) ; championnat : champion 60 M€ + 2 packs Or, podium 35 +
  1 Or, Europe 20 + 2 Argent, première moitié 10 + 1 Argent, maintenu 5
  + 1 Bronze, relégué 2 + 1 Bronze ; coupe d'Europe : vainqueur 90 + 3
  Or, finaliste 55 + 2 Or, demi 36 + 1 Or, quart 24 + 2 Argent, huitième
  15 + 1 Argent, barrages 9, phase de ligue 5 + 1 Bronze.
- Journée fantasy (le mode d'origine) : 0,1 M€ par point au-dessus de
  60, 5 M€ par semaine au plus.
- Lobby classé : rien que l'Elo.
- Marché entre managers : enchères, 5 % de commission ; rachat banque à
  40 % de la cote.

**Ce que ça donne en temps de jeu.** Un championnat, c'est 34 matchs ;
à ×2 un match dure une demi-heure, à ×8 neuf minutes. Une équipe qui
gagne vingt matchs et finit championne touche 30 + 60 = 90 M€ et deux
packs Or : à ×2 c'est **17 heures de jeu pour l'équivalent de deux
packs Or** (3 M€ de l'heure), à ×8 cinq heures (10 M€ de l'heure).
Une carte de 75 (16 M€) toutes les 1 h 30 à 5 h selon le rythme. C'est
lent pour un jeu qui veut récompenser chaque session, et ça ne dépend
pas de la difficulté de la compétition (la Süper Lig paie comme la
Premier League).

## 2. Équilibrer : une seule échelle

Le principe : **tout se compte dans une seule unité, le M€, et tout
s'exprime en « combien de temps pour un pack »**. Trois durées à fixer,
puis tout le reste en découle :

| ce qu'on veut | durée visée | sens |
|---|---|---|
| une récompense visible chaque session | 1 session (un match, 10 à 30 min) → 1 pack Bronze ou l'équivalent | on repart toujours avec quelque chose |
| une carte qui change le onze | 2 h de jeu → 1 pack Or (une carte de 75+) | la progression se voit chaque soir |
| une équipe de niveau européen (75 de moyenne) | 40 à 60 h de jeu, ou 20 à 40 € | le but d'une saison de joueur gratuit |

**Les sources, proposition** (en M€ ; à ajuster avec les durées
ci-dessus) :

- **Par match**, quel que soit le mode, une prime qui dépend du rythme
  choisi (un match de 30 min rapporte plus qu'un résumé de 9 min, sinon
  tout le monde joue à ×8) et du résultat : à ×2, 6 M€ la victoire, 3
  le nul, 1,5 la défaite (on a joué) ; à ×4 la moitié ; à ×8 le quart.
  Et un bonus d'adversité : +50 % contre une équipe mieux classée
  (Elo ou force du club), pour que le fort ne farme pas le faible.
- **Par compétition**, garder l'échelle actuelle (champion 60, LdC 90)
  mais la pondérer par la force du champ : la moyenne d'OVR des clubs de
  la compétition rapportée à 75 (Premier League ×1,2, Eredivisie ×0,8).
- **Lobby classé** : une prime par match (la même grille) et une prime
  de palier d'Elo (1 100, 1 200, …), une fois chacune.
- **Le quotidien** : un pack Bronze offert par jour de connexion, un
  Argent au septième jour d'affilée. C'est le moteur du retour.
- **Les défis** (« gagne avec trois cartes de moins de 65 », « marque
  de la tête ») : des petites primes qui orientent vers des façons de
  jouer, pas vers plus d'heures.

**Les puits** : les packs (prix réglés sur la valeur attendue, voir
§ 3), les enchères entre managers (la commission de 5 % retire de la
monnaie), et la banque qui rachète à **25 %** de la cote (40 %
aujourd'hui), pour qu'ouvrir-revendre perde toujours.

**Le départ** : 100 M€ et 18 cartes à 56 d'OVR, c'est juste : on voit
des cartes qu'on ne connaît pas, et le premier pack Or change quelque
chose. Mieux : **un onze de départ tiré au sort, pas acheté** (18
cartes de 50 à 64, un ou deux « espoirs » de 68-72 pour l'attachement),
plus 30 M€ en caisse pour un premier pack et une première enchère. Le
nouveau joueur n'a pas à comprendre le marché avant son premier match.

**L'inflation.** Une économie de cartes gonfle parce que les packs
créent des cartes et que les primes créent de l'argent. Trois freins :
le plafond de copies par carte (déjà là : max(3, un quart des équipes)),
la banque à 25 %, et la **saison** : à chaque nouvelle saison réelle,
les cartes de la saison passée restent jouables mais cotent moins (le
jeu l'a déjà : le poids de la saison passée). On n'a pas besoin de
remettre les compteurs à zéro.

## 3. Les packs : taille, prix, chances

**Combien de cartes.** Trois cartes, c'est trop peu pour un geste
d'ouverture qui doit faire plaisir, et trop peu pour composer : un pack
de trois ne change pas un onze. Proposition :

| pack | cartes | garanties | prix (M€) | valeur attendue |
|---|---|---|---|---|
| Bronze | 5 | 5 cartes < 60 | 25 | 41 (ratio 1,6) |
| Argent | 5 | 5 cartes 60–74, dont 1 de 70+ | 60 | 75 (1,25) |
| Or | 5 | 1 carte 75+, 1 carte 70+, 3 cartes 60–74 | 90 | 100 (1,1) |
| Élite | 7 | 2 cartes 80+, 2 cartes 75+, 3 cartes 65+ | 250 | 270 (1,08) |
| Poste | comme le pack choisi, un poste | | +20 % | |

Le ratio (valeur attendue / prix) descend quand le pack monte : les
petits packs sont le plaisir fréquent, les gros la vraie dépense ; et
avec la banque à 25 %, aucun pack ne se revend à profit (Bronze : 41 ×
0,25 = 10 M€ contre 25 payés). Un pack à 5 cartes avec une garantie
chiffrée (« dont 1 de 70+ ») se comprend sans lire les probabilités.

**Les chances.** Le tirage uniforme dans un palier donne une carte de
59 aussi souvent qu'une de 45 : bien pour la découverte, mais l'écart
entre un 75 et un 79 (16 M€ contre 20) est plus faible que l'écart de
plaisir. Garder l'uniforme, qui est honnête et simple à afficher
(« une chance sur 271 pour chaque carte Or »), et **afficher les
chances** : c'est obligatoire sur l'App Store et Google Play, et
attendu par la loi dans plusieurs pays (§ 4).

**Les doublons.** Avec un plafond de copies et des packs plus gros, les
doublons arrivent vite. Deux usages, au choix du joueur : la revente
banque (25 %), ou la **fusion** : trois copies d'une carte donnent une
copie « +1 » (un point d'OVR, un liseré), ce qui transforme le doublon
en progression au lieu d'en poubelle. C'est ce qui retient les joueurs
dans les jeux de cartes.

## 4. Argent réel contre argent du jeu

**Le taux.** Il faut un seul taux affiché partout, et qu'un pack acheté
en argent réel coûte **la même chose** qu'en argent du jeu (pas de pack
réservé aux payants, c'est ce qui fait fuir). Proposition : **1 € =
10 M€** (on ne vend pas les M€ au détail : on vend des packs et un
abonnement).

| pack | prix jeu | prix réel | repère du marché |
|---|---|---|---|
| Bronze | 25 M€ | — (jamais vendu : il se gagne) | |
| Argent | 60 | 0,99 € (on arrondit en faveur du joueur) | un « pack de départ » FUT vaut 1 à 2 € |
| Or | 90 | 1,99 € | FUT : pack Or premium ≈ 1,5 € |
| Élite | 250 | 4,99 € | FUT : les gros packs valent 10 à 25 € |
| lot de 3 Or | 270 | 4,99 € | |

Ces prix sont ceux d'un petit jeu indépendant : bas, pour qu'un joueur
achète par plaisir, pas par pression. Le repère EA FC : 100 points = 1 €
environ, un pack Or 7 500 pièces ≈ 150 points ≈ 1,5 € ; nos packs sont
plus gros et moins chers. **Combien ça rapporte** : dans ce genre, 2 à
5 % des joueurs paient, pour 10 à 30 € par an chacun ; mille joueurs
actifs, c'est 300 à 1 500 € par an. L'abonnement (§ 6) pèse plus lourd
et plus régulièrement que les packs.

**Ce que la loi dit des packs payants.** Un pack à contenu aléatoire
acheté avec de l'argent réel est une *loot box* :
- en **Belgique**, c'est un jeu de hasard interdit sans licence depuis
  2018 (EA a retiré les points FIFA du pays) ; aux **Pays-Bas**, la
  justice a finalement donné raison à EA en 2022, mais le sujet revient ;
- **Apple et Google** exigent l'affichage des probabilités de chaque
  objet ; le **PEGI** ajoute la mention « achats intégrés, objets
  aléatoires » ;
- le **Parlement européen** a voté en 2023 pour encadrer (transparence,
  mineurs), sans texte contraignant encore ;
- en France, rien de spécifique à ce jour, mais la question des mineurs
  est sensible.

La position la plus sûre : **l'argent réel n'achète jamais un tirage
aléatoire**. Il achète l'abonnement (§ 6), des M€ qui servent à tout
(packs compris, mais c'est le joueur qui choisit, et ça reste la zone
grise des « monnaies intermédiaires »), et des objets certains :
maillots, écussons, un **choix de carte** (« choisis une carte parmi
cinq de 75+ », qui n'est pas aléatoire). Et au moins : chances
affichées, pas de packs payants proposés aux comptes de mineurs, pas de
compte à rebours (« plus que 2 h ! »). Ça ne remplace pas l'avis d'un
juriste avant la mise en ligne, mais ça fixe le cap.

## 5. Les droits : garder des cartes de joueurs

**Ce qui est protégé, et par qui.**
- **Le nom et l'image des joueurs** : droit à l'image et droit de la
  personnalité, négociés collectivement par la **FIFPRO** (c'est la
  licence d'EA et de Konami ; hors de portée d'un indépendant : des
  millions par an).
- **Les clubs** : noms, écussons, maillots sont des marques (chaque club
  ou ligue les licencie séparément : « Paris Saint-Germain » et son
  écusson sont protégés ; « Paris » ne l'est pas).
- **Les compétitions** : « Ligue 1 », « Champions League » sont des
  marques, avec leurs logos.
- **Les données** : les statistiques d'un match sont des faits, mais la
  base qui les compile est protégée en Europe par le droit *sui generis*
  des bases de données, et les conditions d'utilisation de FotMob
  interdisent la collecte automatique et l'usage commercial. Pour un jeu
  vendu, il faut un fournisseur sous contrat : API-Football ou
  Sportmonks coûtent quelques dizaines à quelques centaines d'euros par
  mois, Opta/StatsPerform des milliers. Le barème (`moteur/`) ne change
  pas : seules les colonnes d'entrée changent de source.
- **Les portraits** : les photos de images.fotmob.com appartiennent aux
  agences et aux clubs. Le jeu ne les transfère déjà jamais (elles sont
  rechargées sur la machine du joueur) ; en ligne, elles ne peuvent pas
  être servies par nous.

**Ce que fait Konami, et pourquoi ça tient.** PES puis eFootball
vendent des équipes sans licence sous des noms génériques (« Manchester
B », « London FC »), avec des joueurs aux noms modifiés, et la
communauté distribue des *option files* qui remettent les vrais noms,
écussons et maillots. L'éditeur ne distribue rien de protégé ; le
joueur modifie sa copie chez lui. C'est exactement le modèle que tu
proposes, et il a vingt ans de pratique derrière lui. Deux réserves : un
nom « partiellement modifié » qui reste reconnaissable (« K. Mbapé »)
est traité comme le vrai nom par les tribunaux (imitation) ; il faut des
noms **différents**, pas déguisés. Et le mod ne doit jamais être
hébergé, lié ou recommandé par nous.

**Proposition pour FootballLife.**
1. **Des cartes de joueurs fictifs, calculées sur le réel.** Chaque
   carte garde son barème (les attributs viennent des vraies
   performances, c'est le cœur du jeu), son poste, son âge, son pied, sa
   nationalité, son physique. Elle reçoit un **nom généré**,
   déterministe (même carte, même nom d'une base à l'autre), tiré de
   listes de prénoms et de noms par nationalité, sans ressemblance
   voulue avec le vrai ; un **club fictif** : le nom de la ville (comme
   PES), un écusson et un maillot dessinés par le jeu (le dessin de
   maillots existe déjà : `MJ.tenues`) ; des **compétitions** nommées
   par le pays (« Championnat d'Angleterre », « Coupe d'Europe »).
2. **Un portrait généré** à partir des données qu'on a : la couleur de
   peau est déjà lue sur le portrait, on garde une palette (peau,
   cheveux, barbe, forme de visage) tirée de manière déterministe, et on
   dessine un avatar dans le style des cartes actuelles. C'est le
   chantier graphique le plus visible ; sans lui, une carte sans photo
   fait pauvre.
3. **Un dossier de mod**, chez le joueur : `mods/noms.csv` (identifiant
   de carte → nom affiché), `mods/portraits/<id>.png`, `mods/clubs.csv`
   (club → nom, couleurs, écusson). Le jeu les lit s'ils existent, sinon
   il affiche le fictif. L'identifiant de carte est stable (c'est déjà
   le `player_id`). Nous ne fournissons pas ces fichiers ; la communauté
   le fera, comme pour PES, et l'outil de téléchargement des portraits
   (`outils/`) devient un outil de mod, pas une partie du jeu.
4. **Les données sous contrat** avant la mise en ligne : brancher un
   fournisseur sur `moteur/importer` (les clés de FotMob sont à
   remplacer par celles du fournisseur ; le barème est le même). En
   attendant, le jeu local reste ce qu'il est.

Ce que ça coûte : le générateur de noms (une journée), le générateur
d'avatars (quelques jours, c'est du dessin), le chargeur de mods (une
journée), le renommage des clubs et compétitions dans les écrans (une
journée). Ce que ça rapporte : un jeu qu'on a le droit de vendre.

## 6. En ligne : gratuit limité, premium

**Le gratuit.** Un compte gratuit joue, progresse et peut tout obtenir
avec du temps. Les limites sont des limites de **rythme**, pas de
contenu :
- 2 matchs par jour en campagne ou en défi, sans limite de matchs
  classés (le classé est ce qui fait vivre le lobby : on ne le freine
  pas) ;
- 1 pack Bronze offert par jour, 1 Argent au septième jour ;
- le marché ouvert, avec 2 enchères en cours au plus.

**Le premium**, un abonnement à **4,99 €/mois** (ou 39,99 €/an) :
- matchs illimités, 3 packs offerts par jour (Bronze, Bronze, Argent),
  10 enchères en cours ;
- +25 % de primes de match (le temps est récompensé un peu mieux, pas
  deux fois plus : un payant qui écrase les gratuits tue le lobby) ;
- les cosmétiques (maillots, écussons, cartes « +1 » visibles), le
  choix de carte mensuel (« une carte parmi cinq de 80+ »).
- Et jamais : une carte ou un attribut que seul l'argent donne.

**Le serveur.** Le moteur B coûte 0,15 s de calcul par minute de match,
14 s par match complet ; un petit serveur (4 cœurs) joue 20 000 matchs
par jour. Les sondages de l'écran (toutes les 2,5 s, 60 Ko) pèsent plus
que le moteur ; à cent joueurs en direct, c'est 2,4 Mo/s. Un VPS à 20
€/mois tient quelques centaines de joueurs simultanés ; au-delà, on
sépare le moteur (plusieurs processus) de l'API. Les portraits ne sont
pas servis (§ 5).

**La mise en ligne**, par étapes : (1) les comptes et l'économie
corrigée (§ 2-3) en local, pour tester les durées sur de vrais
joueurs ; (2) les cartes fictives et le chargeur de mods (§ 5) ; (3) un
serveur fermé pour une centaine de testeurs, gratuits ; (4) l'abonnement.

## 7. Par quoi commencer

1. **Corriger le pack Bronze** et la banque (25 %), et reprixer les packs
   sur leur valeur attendue : une heure, et ça ferme un trou.
2. **Les primes de match** selon le rythme et l'adversité, le pack du
   jour : une demi-journée ; et mesurer les durées (combien de temps pour
   un pack Or) sur une campagne jouée.
3. **Les packs à cinq cartes** avec garanties, les chances affichées,
   la fusion des doublons.
4. **Les cartes fictives et les mods** (§ 5), le gros morceau, avant
   toute mise en ligne.
5. **Les comptes en ligne et le premium** (§ 6).
