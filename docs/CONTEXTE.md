# Contexte du projet — jeu de gestion adossé à un barème réel

Document à donner à Claude Code au démarrage. Il décrit ce qui existe déjà,
ce qu'il faut construire, et les pièges rencontrés.

---

## 1. Le projet

Un jeu de gestion d'effectif où **les points viennent des vraies performances**
des joueurs, mesurées par un barème maison déjà écrit et validé.

Le joueur compose un effectif avec un budget, aligne son onze avant chaque
journée, et récolte les notes réelles calculées après les matchs. Entre les
journées : transferts, gestion de la forme, blessures.

**Ce n'est pas une simulation.** Aucun match n'est inventé : on lit les
données FotMob des matchs réellement joués. C'est ce qui distingue ce projet
d'un Football Manager et ce qui le rend réalisable.

---

## 2. Ce qui existe déjà — et qui est le cœur du projet

### Le barème (`moteur/bareme_stats.py`, `moteur/topsflops.py`)

Note chaque prestation à partir des statistiques de match. Chaque action
rapporte ou coûte des points, pondérés par la compétition et par la force de
l'adversaire.

**Preuve de fiabilité** : appliqué aux six dernières saisons, il retrouve le
vrai vainqueur du Ballon d'Or **cinq fois sur cinq** (Messi 2021, Benzema 2022,
Messi 2023, Rodri 2024, Dembélé 2025), avec en moyenne 6 joueurs sur 10 en
commun avec le vrai top 10.

### Le palmarès (`moteur/palmares_zero.py`)

Valorise les titres et distinctions, pondérés par leur rareté et par la part
réelle du joueur dans le parcours de son équipe.

### La note sur 10

Trois étapes :
1. score brut du barème ;
2. conversion par percentiles **du poste**, mesurés sur 42 000 prestations
   (`moteur/seuils_flops_postes_2526.json`) : p10 = 4, p25 = 5, médiane = 6,
   p75 = 7, p90 = 8 ;
3. amortissement par le temps de jeu : la note s'écarte de 6 à proportion de
   la racine des minutes jouées, pleine à 60 min. Un entrant de 14 minutes ne
   peut pas obtenir 3 ni 9.

### Les attributs de carte (`moteur/echelles_attributs.json`)

Six familles — finition, création, progression, défense, dribble,
conservation — cotées de 40 à 99 sur les percentiles de la saison, avec une
**référence commune à tous les joueurs de champ** (la finition ne dépend pas
du poste). Les gardiens ont leurs propres familles : arrêts, buts évités,
sorties, relance, imbattabilité, progression.

### La carte joueur (`moteur/carte_design.py`)

Module autonome et déjà validé visuellement. Produit une image PNG :
décor de compétition avec logo, fond aux couleurs du maillot, maillage
d'écussons du club en filigrane, portrait recadré sur le visage, jeton
hexagonal de note, bandeau nom/poste/minutes, six attributs.

```python
carte(pid, nom, note, club_couleur, competition, poste, minutes,
      attributs, larg, team_id) -> Image
```

Les logos de ligue sont dans `donnees/ligues/`.

---

## 3. Ce qui reste à construire

### a. Le modèle de données

- joueurs, clubs, compétitions, matchs, prestations
- utilisateurs, effectifs, compositions par journée, transferts
- historique des notes et des valeurs

### b. La valorisation des joueurs

À dériver de la moyenne des notes sur la saison précédente. **À concevoir** :
c'est la décision de game design la plus structurante, elle détermine
l'équilibre économique du jeu.

### c. Le calcul des scores d'équipe

Presque immédiat : le barème produit déjà une note par joueur et par match,
il suffit de sommer sur le onze aligné.

### d. L'interface

Composition d'équipe, marché des transferts, classement. C'est le vrai
chantier de développement.

### e. Les comptes et l'hébergement

Rien n'existe.

---

## 4. Décisions de game design en suspens

Trois questions non tranchées, à poser au porteur du projet :

1. **Budget et valeur des joueurs.** Barème de prix ? Plafond salarial ?
2. **Fréquence.** Chaque journée de championnat, ou plus lent ?
3. **Périmètre.** Ligue 1 seule pour commencer, ou les cinq championnats ?
   *Recommandation : commencer par la Ligue 1.*

---

## 5. Pièges déjà rencontrés — à ne pas refaire

Ces erreurs ont coûté des heures. Elles ont toutes la même forme : **une
correspondance qui échoue en silence, sans message d'erreur**.

- **Homonymes.** Trois joueurs nommés « Rodri », deux « Vitinha », deux
  « Jorginho ». Toute table nom → identifiant construite sur l'ensemble de la
  base écrase les homonymes. Toujours restreindre au périmètre du match.
- **Accents.** La base écrit « Vinicius Junior », les sources officielles
  « Vinícius Júnior ». Toute comparaison de noms doit être normalisée.
- **Libellés.** Le barème ne reconnaît que certaines formes de libellé de
  distinction. Toute autre formulation est ignorée sans avertissement.
- **Finales aux tirs au but.** Le score en base est nul : sans table de
  vainqueurs, personne ne reçoit le titre.
- **Côtés du terrain.** Colonne < 5 = côté droit, > 5 = côté gauche. Deux
  équipes qui se font face ont leurs côtés inversés à l'écran.
- **Doublons de fonctions.** À force de retouches, un fichier peut contenir
  trois définitions de la même fonction ; c'est la dernière qui s'applique.
  **Mettre le projet sous Git dès le premier jour.**

---

## 6. Sources de données

- **FotMob** — feuilles de match complètes, via une collecte maison. xG
  disponible à partir de la saison 2020/21 seulement.
- **FBref** (base `master.db`) — couche de progression : passes progressives,
  conduites, zones. Couvre cinq championnats, 2017/18 à aujourd'hui.
- Bases par saison disponibles : 2017/18 à 2025/26.

---

## 7. Conseil de démarrage

Poser l'architecture avant d'écrire du code : modèle de données, choix de
la base, découpage front/back. Le moteur de notation étant déjà écrit et
testé, il faut le traiter comme une bibliothèque et ne pas le réécrire.
