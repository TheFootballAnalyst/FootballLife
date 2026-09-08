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

En dessous de p10, la même courbe en miroir est appliquée. Ce n'est **pas
couvert** par le fichier de référence (qui ne contient que des tops) : un
échantillon de flops permettrait de le vérifier.

## Protocole

Pas de base 2024/25 disponible, donc la saison est coupée en deux :

| | journées | rôle |
|---|---|---|
| amorce | J1 à J17 | tient lieu de « saison précédente » pour valoriser les cartes |
| jeu | J18 à J34 | 17 journées jouées par des managers scriptés |

Périmètre : les 462 joueurs des clubs de Ligue 1, avec leurs matchs de
Ligue 1 et de C1. Une journée de jeu = du premier coup d'envoi d'une
journée de L1 à la veille de la suivante (le milieu de semaine européen
compte dans la journée qui le précède).

Quatre managers, tous à 40 crédits, 15 cartes, 4-3-3 :

- **naïf** achète les meilleurs OVR qu'il peut se payer, aligne par OVR ;
- **forme** achète les cartes dont la forme récente (5 dernières
  prestations) dépasse ce que leur OVR a déjà intégré, et réajuste chaque
  semaine ;
- **oracle** connaît l'avenir et achète les meilleurs points par crédit :
  une borne haute, pas une stratégie ;
- **hasard** ×5, effectif légal tiré au sort.

## Réglages retenus

| constante | valeur | pourquoi |
|---|---|---|
| échelle OVR | calibrée sur le périmètre : p2 des moyennes → 40, p99,5 → 99 (L1 25/26 : 4,84 → 7,21) | les moyennes de saison sont resserrées, et la Ligue 1 note plus bas que la Premier League par construction du barème |
| prior / K | 5,5 / 10 matchs pleins | un inconnu est bon marché |
| EMA | α = 0,08, pondéré par minutes/60 | à 0,12 les prix bougeaient d'une bande par match |
| prix | ×2 tous les 8 OVR, plancher 0,5 | pente 6 rend les hausses trop lucratives (valeur ×4 en 17 journées) |
| budget | **40** | le meilleur 15 du périmètre coûte 64 ; à 60 ou 100 le naïf l'achète et fait jeu égal avec l'oracle |

## Résultats (J18–J34)

| manager | points | valeur finale (départ 40) |
|---|---|---|
| oracle | 1 211 | 61 |
| **forme** | **1 020** | **92** |
| naïf | 947 | 63 |
| hasard (moyenne de 5) | 687 | 43 |

Réponses aux quatre questions de `GAME_DESIGN.md` :

1. **L'informé bat le naïf**, de 8 % en points et de 45 % en valeur. Le
   hasard est loin derrière. L'oracle garde une marge de 19 % sur
   l'informé : il reste quelque chose à savoir. C'est l'ordre voulu.
2. **Plancher / plafond.** 100 titulaires (≥ 450 min) finissent au prix
   plancher de 0,5, soit le cinquième bas du périmètre : indifférencié mais
   pas gênant. Deux cartes touchent 99 (voir ci-dessous).
3. **Score d'équipe.** Médiane 44 par journée, loin des 66 visés, parce
   que les managers scriptés alignent par OVR sans regarder qui joue :
   0,9 à 2 remplacements automatiques par journée. Un humain fera mieux ;
   `SCORE_REFERENCE = 60` est donc à revoir une fois des vrais managers
   observés.
4. **Banc.** Les remplacements automatiques se déclenchent presque chaque
   journée ; l'ordre du banc compte.

## La découverte qui compte : le PSG

Les huit plus fortes hausses de prix entre J17 et J34 sont **toutes** des
joueurs du PSG :

| joueur | OVR J17 → J34 | prix |
|---|---|---|
| Ousmane Dembélé | 69 → 99 | 2,2 → 29,3 |
| Nuno Mendes | 83 → 99 | 7,3 → 29,3 |
| João Neves | 76 → 96 | 4,0 → 22,6 |
| Kvaratskhelia | 74 → 94 | 3,4 → 19,0 |
| Désiré Doué | 60 → 89 | 1,0 → 12,3 |

Ce n'est pas la forme : c'est le barème. Le coefficient de compétition
(C1 = 2,0) multiplié par le coefficient de tour (finale = 2,2) est *dans*
la note. Un match de phase finale de C1 vaut jusqu'à 4,4 fois un match de
Ligue 1, et le seul club de Ligue 1 qui va au bout est le PSG. Dans une
ligue de jeu limitée à la Ligue 1, la stratégie dominante au printemps est
« acheter du PSG », et l'informé le fait mécaniquement.

C'est cohérent avec ce que le barème veut mesurer pour un Ballon d'Or.
C'est discutable pour un jeu où l'on veut récompenser la connaissance
des joueurs à bas prix. Trois options, à trancher :

- **a.** Assumer : la C1 est le sommet, les cartes qui y brillent valent
  cher. Le jeu récompense alors surtout d'anticiper les parcours européens.
- **b.** Plafonner le coefficient de tour dans la note *du jeu* (par
  exemple 1,3 au lieu de 2,2 en finale) tout en gardant le coefficient de
  compétition. Le moteur ne change pas ; seule la couche jeu lit un
  `coef` borné.
- **c.** Élargir le périmètre aux cinq championnats + C1 dès la première
  saison, où plusieurs clubs vont loin en Europe et l'effet se dilue.

Recommandation : **b** pour une ligue Ligue 1, **a** pour une ligue Top 5.
Le backtest peut chiffrer les deux en une minute.

## Limites du protocole

- L'amorce sur une demi-saison sous-estime les échantillons : avec une
  vraie saison précédente, K = 10 pèsera moins et les OVR de départ seront
  plus étalés.
- Les managers scriptés ne regardent ni les blessures ni les calendriers ;
  leurs scores absolus sont bas. Les écarts *entre* stratégies sont ce qui
  compte.
- La courbe de note sous p10 n'est pas vérifiée contre la chaîne de
  visuels.

## Reproduire

```
python3 -m jeu.importer --fotmob moteur/fotmob.db --jeu jeu/jeu_2526.sqlite
python3 -m jeu.backtest --amorce 1-17 --jouer 18-34 --sortie out/
```

Les constantes se changent dans `jeu/evolution.py` ; `out/resume.json`
rappelle celles qui ont servi.
