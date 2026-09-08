# Moteur de notation — bibliotheque a ne pas reecrire

Ces fichiers viennent d'un projet existant, valide sur six saisons. Ils
constituent le coeur du jeu.

| fichier | role |
|---|---|
| `bareme_stats.py` | table des points par action, coefficients, calibration |
| `topsflops.py` | calcule les prestations d'une periode a partir d'une base FotMob |
| `palmares_zero.py` | valorise titres et distinctions |
| `carte_design.py` | fabrique l'image d'une carte joueur |
| `bareme_stats_coefs.json` | coefficients de championnat mesures |
| `seuils_flops_postes_2526.json` | percentiles par poste, pour la note sur 10 |
| `echelles_attributs.json` | percentiles par famille, pour les six attributs |

## Dependances

`Pillow` pour les images, `sqlite3` (standard). Le barème lit une base
FotMob au format maison — schema : tables `match`, `appearance`, `player`,
`stat`, plus les vues `v_match`, `v_appearance`, `v_stat`.

## Points d'entree utiles

```python
# prestations d'une periode -> topsflops.json
python3 topsflops.py --du 2026-09-01 --au 2026-09-08 --json

# une carte
from carte_design import carte
im = carte(pid, nom, note, "#0B4EA2", "Ligue 1", "Ailier", 90, attributs, 420, team_id)
```

## Ce qu'il ne faut pas toucher

La table des points et les percentiles. Ils sont calibres sur 42 000
prestations ; les modifier invalide la note sur 10 et les attributs, et il
faudrait tout recalculer.
