# En ligne : les comptes, le gratuit, le premium, le paiement

Ce que le chantier 5 (PLAN.md) a mis en place, et comment le lancer.

## Les comptes

- **L'inscription** demande un pseudo et un mot de passe ; le courriel et la
  date de naissance sont facultatifs. Le courriel sert au mot de passe
  oublié ; la date de naissance dit si le compte est celui d'un mineur : il
  joue, il n'achète pas (`jeu/comptes.AGE_ACHAT`).
- **Un seul club par compte** (la contrainte est en base).
- **Le mot de passe oublié** : « Mot de passe oublié ? » sur l'écran de
  connexion → un lien valable 24 h, envoyé par courriel si un serveur SMTP
  est configuré, sinon écrit dans le journal du serveur (l'administrateur
  le transmet). Le lien ouvre le site avec `?mdp=<jeton>` et demande le
  nouveau mot de passe. L'outil `web/app/mdp.py` reste là pour une base
  locale.

Variables : `FL_SMTP_HOTE`, `FL_SMTP_PORT` (587), `FL_SMTP_UTILISATEUR`,
`FL_SMTP_MDP`, `FL_SMTP_DE`, et `FL_URL` (l'adresse publique du site, pour
les liens).

## Le gratuit et le premium

Les limites ne s'appliquent que si la base le dit : `lancer.py --limites`
ou `FL_LIMITES=1`. Sans, le jeu local reste sans limite.

| | gratuit | premium (4,99 €/mois, 39,99 €/an) |
| --- | --- | --- |
| matchs de campagne ou de défi par jour | 2 | illimités |
| matchs classés | illimités | illimités |
| enchères en cours | 2 | 10 |
| packs du jour | 1 Bronze (1 Argent au 7ᵉ jour) | Bronze + Bronze + Argent |
| primes de match | ×1 | ×1,25 |

Jamais une carte ou un attribut que seul l'argent donne. Les chiffres sont
dans `jeu/comptes.GRATUIT` et `PREMIUM`, mesurés à régler après le test
fermé (chantier 1.6).

## Le paiement

`jeu/paiement.py`. Deux fournisseurs :

- **Stripe** (Checkout) quand `FL_STRIPE_SECRET` est posé : l'écran Compte
  envoie le joueur sur la page de paiement Stripe ; le webhook
  `/api/paiement/stripe` (signé par `FL_STRIPE_WEBHOOK`, événement
  `checkout.session.completed`) livre l'achat, une seule fois par
  référence.
- **manuel**, sans clé : rien ne se vend, l'administrateur accorde le
  premium à la main (`POST /api/admin/premium {pseudo, duree}`), pour un
  test fermé.

Les produits (`jeu/paiement.PRODUITS`) : premium un mois ou un an, et des
M€ (50, 100, 250 : 1 € ≈ 10 M€, ECONOMIE.md § 4). Pas de pack vendu en
argent réel : un pack coûte la même chose pour tout le monde, en M€.

## Le serveur

- `Dockerfile` à la racine, la base dans un volume (`/data/jeu.sqlite`),
  `FL_SECRET` obligatoire ; les variables ci-dessus en plus.
- **Le monde fictif** pour la version en ligne : `py jeu/fictif.py --fictif
  --jeu /data/jeu.sqlite` avant le premier lancement (`docs/MODS.md`).
- **Les sauvegardes** : `py outils/sauvegarde.py --jeu /data/jeu.sqlite`
  fait une copie cohérente pendant que le site tourne, et garde les 14
  dernières ; à mettre dans un cron, une fois par heure suffit.
- **Les mises à jour sans couper un match** : un match vivant est une
  fonction de sa graine et de sa chronologie (jeu/direct.py) ; un serveur
  redémarré le rejoue à l'identique jusqu'à la minute de l'horloge. On
  peut donc redéployer à tout moment ; les écrans se resynchronisent au
  sondage suivant.
- **La charge** (ECONOMIE.md § 6) : un VPS à 4 cœurs tient quelques
  centaines de joueurs simultanés ; au-delà, séparer le moteur de l'API.

## Le test fermé

Une centaine de joueurs gratuits, un mois, limites actives, paiement
manuel : on lit les durées (combien de temps pour un pack Or, chantier
1.6), les primes, le rythme, et on règle `comptes.py` et `marche.py`
avant d'ouvrir le paiement.
