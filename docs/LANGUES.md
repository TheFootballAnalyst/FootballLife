# Les langues

Le jeu se traduit sans toucher au code (PLAN.md § 3). Le français est la
langue source ; l'anglais est la langue pivot (toute traduction suivante
part de l'anglais).

## Où sont les textes

| Quoi | Où | Comment |
| --- | --- | --- |
| L'écran (boutons, panneaux, aides, toasts) | `web/app/static/lang/<code>.json` | une clé → un texte, `{param}` pour les paramètres, `{"1": …, "n": …}` pour le pluriel (sur le paramètre `n`) |
| `index.html` | les attributs `data-t`, `data-t-placeholder`, `data-t-title` | la clé pointe dans le même dictionnaire |
| Les erreurs du serveur et des règles | `jeu/messages.py` (le français de secours) et les clés `err.<code>` | l'API renvoie `{"code", "params", "message"}`, l'écran traduit |
| Le commentaire du match (moteur B) | `direct._gabarit` → clés `evt.<clé>` | la feuille porte la clé et ses paramètres (`gab`), l'écran met en phrase |
| Le style d'un onze, la lecture de l'adversaire, les objectifs, les récompenses, les phases | codes à côté du français (`style_codes`, `lecture_codes`, `objectif.code`, `bilan.code`) | clés `style.*`, `lecture.*`, `obj.*`, `recompense.*`, `phase.*` |
| La boîte de dialogue | `jeu/dialogue.py`, `VOCABULAIRE[<code>]` | des motifs (expressions régulières sur la phrase normalisée) et les phrases de confirmation |
| Les noms de joueurs, de clubs, de compétitions | — | ne se traduisent pas |
| Le commentaire du moteur A | `jeu/simulation.py` | reste en français jusqu'au retrait du moteur A (chantier 6) |

Les codes de poste sur les cartes (GB, DC, MOC…) sont ceux des cartes
dessinées : ils ne changent pas avec la langue, seul leur libellé change
(`code.<code>`).

## Ajouter une langue

1. Copier `web/app/static/lang/en.json` en `<code>.json` et traduire les
   valeurs (jamais les clés, jamais les `{paramètres}`). Le test
   `jeu/tests/test_langues.py` vérifie que chaque langue a exactement les
   clés du français, avec les mêmes paramètres.
2. L'ajouter à `LANGUES` dans `app.js` (le nom affiché dans le sélecteur)
   et à `LOCALES` (le format des nombres et des dates).
3. Pour la boîte de dialogue : une table `VOCABULAIRE["<code>"]` dans
   `jeu/dialogue.py`, sur le modèle de l'anglais. Sans table, la boîte
   répond dans la langue de secours.
4. Faire jouer un natif une campagne et corriger : un jeu traduit sans
   joueur se repère en trois écrans.

## Le choix de la langue

Le sélecteur est dans la barre. Le choix est gardé dans le navigateur
(`fl_langue`) ; sans choix, c'est la langue du navigateur, et le français
si elle n'est pas couverte. Le serveur ne garde pas la langue : il parle
en codes, et c'est l'écran qui traduit.

## La pseudo-traduction

Dans la console du navigateur : `localStorage.setItem("fl_langue", "xx")`
puis recharger. Chaque texte français est allongé de 30 % avec des accents
(« Cømpøsïtïøñ ~~~~ ») : ce qui déborde ou se coupe se voit tout de suite.
Un `{paramètre}` qui apparaît tel quel à l'écran est un texte qui ne passe
pas par `t()`.

## Vérifier dans un navigateur

`jeu/tests/test_langues.py` tient les dictionnaires cohérents ; pour voir
les écrans, un passage dans Chromium (Playwright) sur chaque écran dans
chaque langue, sans erreur JavaScript, est ce qui a servi à livrer le
chantier (le script n'est pas dans le dépôt : il dépend du navigateur
installé).
