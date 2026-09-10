# Backtest — saison 2025/26 rejouée hors ligne

Phase 1 de `ROADMAP.md`. Tout ce qui suit sort de :

```
python3 -m jeu.importer            # fotmob.db -> jeu/jeu_2526.sqlite (1 min 30)
python3 -m jeu.backtest            # -> out/cartes.csv, out/managers.csv, out/resume.json (0,2 s)
```

## Ce qui a été validé avant de jouer

**La note et les attributs reproduisent la chaîne de visuels à l'identique.**
Sur les 40 prestations de référence du 28/08 au 06/09/2026 : 40/40 notes
exactes, 240/240 attributs exacts. Le fichier est dans
`jeu/tests/donnees/` et le test tourne à chaque `pytest`.

Trois choses ont dû être corrigées pour y arriver, toutes documentées
dans `jeu/notation.py` :

- l'entrée de la note est `points` (brut × coefficient de poste), comparé
  aux seuils tels quels ;
- au-delà de p90 la courbe sature : `note = 8 + 2u/(1+u)` avec
  `u = (points − p90)/(p90 − médiane)`. Bruno Fernandes à 138 points fait
  9,5, pas 12 ;
- les attributs prennent les lignes telles que le moteur les écrit, sans
  rien diviser.

## Vérification sous p10

Ton échantillon de flops (65 prestations : les 40 pires du week-end, des
entrants de moins de 30 minutes, des joueurs exactement au p10, des
gardiens en négatif) a donné la règle exacte :
`note = max(1, 4 − 3 × min(écart, 1))` avec `écart = (p10 − points) /
|médiane − p10|`. 65/65 notes et 65/65 attributs exacts. Le fichier est
dans `jeu/tests/donnees/` avec les tops ; le test de régression couvre les
deux.

## Protocole

Pas de base 2024/25 disponible, donc la saison est coupée en deux :

| | journées | rôle |
|---|---|---|
| amorce | J1 à J17 | tient lieu de « saison précédente » pour valoriser les cartes |
| jeu | J18 à J34 | 17 journées jouées par des managers scriptés |

Périmètre retenu : **ligue globale**, les 2 371 joueurs des clubs des cinq
championnats, avec leurs matchs de championnat et de C1 (option a,
décision du porteur). Une journée de jeu = du premier coup d'envoi d'une
journée de Ligue 1 à la veille de la suivante ; les cinq championnats
jouent le même week-end, le milieu de semaine européen compte dans la
journée qui le précède.

Quatre managers, 15 cartes, 4-3-3, tous recrutés par la même règle
(maximiser la valeur totale sous budget et quotas, glouton lagrangien) ;
seule la *valeur* qu'ils donnent à une carte diffère :

- **naïf** : l'OVR, ce que le marché dit déjà ;
- **forme** : la production récente, points par journée sur les cinq
  dernières, absences comptées 0, avec un échantillon minimal de trois
  matchs pleins. C'est le manager qui sait qui produit vraiment ; il
  réajuste chaque semaine ;
- **oracle** : la production future sur la moitié jouée, une borne haute ;
- **hasard** ×5, effectif légal tiré au sort.

Une première version du manager « forme » cherchait les cartes dont la
forme dépassait l'OVR : sur 462 cartes de Ligue 1 ça marchait, sur 2 371
ça ramassait des coups de chance sur trois matchs et finissait au niveau
du hasard. Le critère de production avec échantillon a réglé le problème
aux deux périmètres.

## Réglages retenus

| constante | valeur | pourquoi |
|---|---|---|
| échelle OVR | calibrée sur le périmètre : p2 des moyennes → 40, p99,5 → 99 (global 25/26 : 4,90 → 7,69 ; Ligue 1 seule : 4,84 → 7,21) | les moyennes de saison sont resserrées, et chaque périmètre a sa distribution |
| prior / K | 5,5 / 10 matchs pleins | un inconnu est bon marché |
| évolution | **barème de saison** (`jeu/bareme.py`) : la carte part du total Ballon d'or de la saison passée (60 % barème par 90, 40 % palmarès) placé sur une cloche par rang parmi les réguliers ; en saison la part terrain suit les journées, la saison passée pesant 0,5 ; OVR borné à ±10 du départ | la moyenne glissante des notes prédisait la suite à 0,26, le barème à 0,47 (section ci-dessous) ; l'EMA à 8 % faisait ×14 sur Dembélé en une demi-saison |
| prix | départ = valeur marchande réelle (FotMob) à la date d'amorce, puis ×2 tous les 8 OVR gagnés, plancher 0,1 M€ | pente 6 rend les hausses trop lucratives |
| budget | **100 M€** | l'ordre informé > naïf > hasard tient de 60 à 250 M€ (tableau ci-dessous) ; 100 est un budget de club lisible |

## Choix du mécanisme d'évolution (J18–J34, mêmes cartes, mêmes managers)

Six mécanismes rejoués sur la même amorce. Le « swing » est l'écart
max-min d'OVR sur la demi-saison pour les joueurs à 600 min et plus ; ρ
est la corrélation de rang entre l'OVR à J26 et la production J27–J34.

| mécanisme | forme | patrimoine forme | swing médian | p90 | > 15 | ρ | Dembélé J17 → J34 |
|---|---|---|---|---|---|---|---|
| EMA 8 % (ancien) | 1 489 | 202 | 9 | 16 | 12 % | 0,26 | 64 → 95, 98 → 1 435 M€ |
| EMA 4 % | 1 409 | 180 | 5 | 10 | 1 % | 0,27 | 64 → 84 |
| EMA 8 % bornée ±10 | 1 462 | 165 | 9 | 12 | 1 % | 0,26 | 64 → 74 |
| moyenne glissante | 1 428 | 180 | 5 | 9 | 1 % | 0,26 | 64 → 85 |
| carte fixe | 1 454 | 145 | 0 | 0 | 0 | 0,24 | 64 → 64 |
| **moyenne glissante bornée ±10 (retenu)** | **1 460** | **174** | **4** | **9** | **0 %** | — | 64 → 74, 98 → 233 M€ |

Les points des managers ne dépendent pas du mécanisme (naïf 1 235,
oracle 1 620 partout) et l'OVR qui bouge ne prédit pas mieux l'avenir
qu'une carte fixe : l'évolution est un jeu économique, pas de
l'information. Le mécanisme retenu garde une plus-value réelle (forme
174 contre 145 pour une carte fixe) sans les excès de l'EMA.

## L'OVR sur le barème de saison (J25 → J34, 2 371 cartes)

Le mécanisme retenu remplace la moyenne glissante des notes par le barème
de saison du moteur (`moteur/bareme_stats.py`, celui du Ballon d'or
maison), branché par `jeu/bareme.py`. Vérifications, sur la base 2025/26 :

**Reproduction du Ballon d'or.** Sur les 1 138 joueurs du panel (2 300
minutes, plus les distinctions majeures que le moteur exempte de seuil :
c'est ce qui garde Messi, 1 990 minutes de club et équipe-type de la
Coupe du monde), le score terrain S du jeu est corrélé à 0,999 au par 90
du moteur. Comparé au fichier de référence `ballondor_top30.json` :

| | |
|---|---|
| joueurs communs dans le top 30 | 28 / 30 |
| écart moyen de place | 1,8 |
| corrélation de rang | 0,970 |
| podium | identique (Dembélé, Olise, Mbappé) |

Les deux entrants du jeu, Julián Álvarez (19e) et Federico Valverde
(29e), prennent la place de joueurs classés 31e et au-delà dans le
fichier ; les plus gros écarts sont Emiliano Martínez (+6) et Vitinha
(−4). Les écarts résiduels de par 90 (Kane −1,4, Messi +4,4, Haaland
−0,7) viennent de la version du moteur : le fichier de référence a été
produit avec un `bareme_stats.py` antérieur aux réglages du 27/08/2026
(poids des duels défensifs ramené de 8,0 à 3,0, duels au sol neutralisés,
corrections rendues à leur famille).

**La cloche.** Total hybride placé par rang parmi les 1 782 réguliers
(≥ 900 min) des cinq championnats, cloche 65 ± 10 : 47 cartes à 85 et
plus, 307 à 75 et plus, 1 014 entre 60 et 74, 1 050 sous 60 ; sommet à 98
(Olise, Dembélé). Une échelle linéaire sur le total donnait 1 248 cartes
entre 40 et 44 et 34 à 75 et plus : la queue du palmarès écrasait tout.

**Amplitude de l'évolution.** Saison rejouée avec une amorce sur J1–J25
(terrain seul, comme la démo) puis neuf journées calculées par le
pipeline : ΔOVR p5 −8, p25 −4, médiane 0, p75 +2, p95 +10 ; 120 cartes
butent sur +10, 79 sur −10, 802 bougent d'au moins 5, 2 010 d'au moins 1.
Les plus fortes hausses sont des jeunes partis de 40 (aucune
titularisation) qui se mettent à jouer ; les plus fortes baisses des
titulaires devenus remplaçants (Hrádecký 75 → 65, Trippier 77 → 67). Les
prix suivent : médiane ×1,00, p5 ×0,50, p95 ×2,36. Avec une amorce sur une
saison entière, la saison passée pèse plus et ces amplitudes se
resserrent.

**Prédiction.** Le score terrain de l'amorce prédit le par 90 des neuf
journées suivantes à 0,47 (1 202 joueurs à 450 min et plus après J25),
contre 0,26 pour la moyenne glissante des notes.

**Attributs.** Six axes de points d'actions par 90, classés parmi tous les
joueurs de champ réguliers : Mbappé FIN 99 DRI 98 DEF 43, Van Dijk DEF 98
DRI 49, Saliba DEF 99 FIN 51, Vitinha PRO 99 CON 99. La première version
(corrections relatives au poste incluses) donnait Mbappé 93 en défense.

## Le match en face à face (J18–J34, 40 équipes, 340 matchs)

Quarante effectifs tirés comme la foule (OVR bruité, 100 M€), appariés
au hasard chaque journée, leurs onze passés par les remplacements
automatiques. Buts réels par onze et par journée : moyenne 1,39, médiane
1 ; tirs cadrés 3,8 ; travail défensif 98 points (p10 35, p90 164).

Avec les buts réels seuls, 33 % de nuls avant même la défense : trop peu
de buts. Une chance supplémentaire par K tirs cadrés non convertis, une
annulation par `seuil` points défensifs :

| K | seuil | buts / équipe | nuls | 0-0 | ≥ 4 buts | meilleur score fantasy gagne | la défense change le résultat |
|---|---|---|---|---|---|---|---|
| 3 | 60 | 1,17 | 41 % | 20 % | 11 % | 78 % | 31 % |
| **3** | **80–100** | **1,40–1,58** | **31 %** | **14–9 %** | **14–16 %** | **73–71 %** | **24–16 %** |
| 4 | 100 | 1,37 | 34 % | 13 % | 13 % | 72 % | 15 % |
| 6 | 130 | 1,34 | 33 % | 10 % | 11 % | 73 % | 12 % |

Retenu : K = 3, seuil = 90 avec la famille Défense d'origine ; **70** depuis
que « Duel au sol gagné » l'a quittée (travail défensif moyen par onze
passé de 98 à 77 points), pour garder la défense décisive sur un match
sur cinq. Le football réel fait 1,4 but par équipe et 25 % de nuls ; ici
un défenseur central rapporte quelque chose au-delà de sa note.

## Résultats en euros, ligue globale (J18–J34, budget 100 M€, demande 1,0)

Prix de départ = valeur marchande connue à la fin de J17 (pas de regard
sur l'avenir), 72 cartes sur 2 371 estimées d'après l'OVR.

| manager | points | patrimoine final (départ 100 M€) |
|---|---|---|
| oracle | 1 617 | 220 |
| **forme** | **1 460** | **174** |
| naïf | 1 233 | 133 |
| hasard (moyenne de 5) | 682 | 112 |

Sensibilité au budget (points) :

| budget | naïf | forme | oracle | hasard (moy.) |
|---|---|---|---|---|
| 60 M€ | 1 277 | 1 446 | 1 563 | 677 |
| 100 M€ | 1 235 | 1 489 | 1 626 | 690 |
| 150 M€ | 1 217 | 1 449 | 1 692 | 676 |
| 250 M€ | 1 426 | 1 545 | 1 763 | 724 |

Le naïf (achète par OVR) souffre plus qu'en crédits : les stars coûtent
leur vrai prix, il lui reste moins pour le reste de l'effectif. Le forme
(achète la production récente) garde 20 % d'avance, et le hasard est à
moitié. Les cartes les plus détenues par la foule finissent chères (van
Dijk : 62 % des équipes, 10 → 35 M€), ce qui est l'effet recherché.

## Résultats en crédits (historique : J18–J34, budget 60)

| manager | points | valeur finale (départ 60) |
|---|---|---|
| oracle | 1 980 | 237 |
| **forme** | **1 810** | **206** |
| naïf | 1 392 | 143 |
| hasard (moyenne de 5) | 732 | 62 |

Même ordre en Ligue 1 seule à 40 crédits : oracle 1 609, forme 1 496,
naïf 1 037, hasard 687.

Réponses aux quatre questions de `GAME_DESIGN.md` :

1. **L'informé bat le naïf**, de 30 % en points et de 44 % en valeur. Le
   hasard est loin derrière. L'oracle garde 9 % sur l'informé : il reste
   quelque chose à savoir. C'est l'ordre voulu.
2. **Plancher / plafond.** 551 titulaires (≥ 450 min) sur 2 371 finissent
   au prix plancher de 0,5, le quart bas du périmètre : indifférencié mais
   pas gênant. Six cartes touchent 97 et plus, quatre sont écrêtées à 99
   (Kane, Kimmich, Gabriel, Yamal) : les parcours de C1 du printemps
   dépassent le haut de l'échelle calibrée sur la première moitié. Avec
   une vraie saison d'amorce le haut sera mieux placé.
3. **Score d'équipe.** Médiane 51 par journée, sous les 66 visés, parce
   que les managers scriptés alignent sans regarder qui joue : 0,6 à 1,7
   remplacements automatiques par journée. `SCORE_REFERENCE = 60` est à
   revoir une fois des vrais managers observés.
4. **Banc.** Les remplacements automatiques se déclenchent presque chaque
   journée ; l'ordre du banc compte.

## La C1 dans la note, périmètre global

En Ligue 1 seule, les huit plus fortes hausses étaient toutes des joueurs
du PSG (coefficient de compétition 2,0 × coefficient de tour jusqu'à 2,2,
tous deux dans la note). En ligue globale l'effet se répartit :

| joueur | OVR J17 → J34 | prix |
|---|---|---|
| William Saliba | 72 → 98 | 2,8 → 26,9 |
| Joshua Kimmich | 81 → 99 | 6,2 → 29,3 |
| Ousmane Dembélé | 64 → 95 | 1,4 → 20,7 |
| Julián Álvarez | 67 → 93 | 1,8 → 17,4 |
| Elliot Anderson | 79 → 94 | 5,2 → 19,0 |

Arsenal, Bayern, Barcelone, PSG, Atlético, Nottingham : le printemps
européen reste le moteur des plus-values, mais il n'y a plus un seul club
à acheter. Le porteur a tranché pour cette option (a) : le barème reste
tel quel, la C1 est le sommet et anticiper les parcours européens fait
partie du jeu.

## Trois façons de créer de la rareté (après le prototype)

Le prototype a montré qu'avec une offre illimitée on s'offre plusieurs
stars dès le premier jour. Trois mécaniques ont été ajoutées au backtest
et comparées sur la même saison (ligue globale, J18–J34) :

| mécanique | commande | naïf | forme | oracle | hasard | verdict |
|---|---|---|---|---|---|---|
| référence, offre illimitée | `--mode marche` | 1 392 | 1 810 | 1 980 | 732 | l'ordre voulu, mais les stars sont à tout le monde |
| salaires 2 % de la valeur de l'effectif par journée | `--salaires 0.02` | 1 392 | 1 669 | 1 980 | 732 | ne change pas les points, assèche surtout celui qui échange ; patrimoine de l'informé 206 → 112 |
| ligue de 10 à draft, un propriétaire par carte **dans la ligue** | `--mode draft --managers 10` | 1 294–1 553 | 1 514–1 534 | 1 896–1 922 | 561–1 017 | l'informé ne bat plus le naïf que d'un cheveu, parfois pas : les producteurs sont tous pris, il ne peut échanger qu'avec les agents libres |
| prix qui montent avec la demande d'une foule de 200 managers | `--demande 1.0` | 1 331 | 1 772 | 1 975 | 732 | l'ordre tient, les favoris de la foule doublent de prix (Rice 29, Kimmich 34), le naïf ne peut plus s'offrir le meilleur 15 (patrimoine 143 → 86) |

À `--demande 2.0` et `4.0` l'ordre tient encore (forme 1 718 puis
1 622 contre naïf 1 469 puis 1 314). La part de détention maximale d'une
carte dans la foule simulée est de 18 %, parce que chaque manager a son
propre avis ; dans un vrai jeu elle sera plus concentrée et l'effet plus
fort à coefficient égal.

**Lecture.** Les salaires sont à écarter. La draft en ligue de 10 est un
bon format social mais elle passe l'avantage au tirage au sort de l'ordre
de draft et bride l'informé. Les prix à la demande sont la seule
mécanique qui reste mondiale, sans limite de managers, et qui garde
l'ordre hasard < naïf < informé < oracle : c'est celle retenue
(`GAME_DESIGN.md`).

## Limites du protocole

- L'amorce sur une demi-saison sous-estime les échantillons : avec une
  vraie saison précédente, K = 10 pèsera moins et les OVR de départ seront
  plus étalés, et le haut de l'échelle sera mieux placé.
- Les managers scriptés ne regardent ni les blessures ni les calendriers ;
  leurs scores absolus sont bas. Les écarts *entre* stratégies sont ce qui
  compte.

## Reproduire

```
python3 -m jeu.importer --fotmob moteur/fotmob.db --jeu jeu/jeu_2526.sqlite
python3 -m jeu.backtest --ligue 0 --amorce 1-17 --jouer 18-34 --sortie out/
python3 -m jeu.backtest --ligue 53 ...          # Ligue 1 seule, pour comparer
```

Les constantes se changent dans `jeu/evolution.py` ; `out/resume.json`
rappelle celles qui ont servi.
