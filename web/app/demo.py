"""demo.py — prepare a demo game base from the 2025/26 season.

    python3 web/app/demo.py [--source jeu/jeu_2526.sqlite] [--sortie jeu/demo.sqlite] [--amorce 1-25]

The demo season is 2025/26 itself: cards seeded on J1-J25 (as if that were
last season; a longer seed gives credible cards, Dembélé's autumn injury
no longer prices him as an unknown), the market open at J26, and every
later gameweek's rated
performances already in the base.  The admin advances the season from the
site (Admin → clôturer la journée) without uploading anything, which
makes a multi-player demo possible before the live season.

Compositions, teams and accounts of the source base are dropped.
"""
import argparse
import pathlib
import shutil
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from jeu import backtest as BT  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import pipeline as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--sortie", default=str(RACINE / "jeu" / "demo.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    ap.add_argument("--amorce", default="1-25")
    ap.add_argument("--fotmob", default=str(RACINE / "moteur" / "fotmob_2526.db"),
                    help="FotMob base used to build the game base if --source is missing")
    a = ap.parse_args()
    src, dst = pathlib.Path(a.source), pathlib.Path(a.sortie)
    if not src.exists():
        fot = pathlib.Path(a.fotmob)
        if not fot.exists():
            sys.exit(f"La base du jeu {src} n'existe pas, et la base FotMob {fot} non plus.\n"
                     f"Récupère la release data-2025-26 (docs/GUIDE_DEBUTANT.md, étape 6), puis relance.")
        print(f"La base du jeu {src} n'existe pas : import de la saison depuis {fot} (environ 1 min 30)...")
        I.main_import(fot, src, a.saison)
    if dst.exists():
        dst.unlink()
    shutil.copy(src, dst)
    jeu = I.ouvrir_jeu(dst)
    # a game base written before market values existed: read them from the cached sheets
    if jeu.execute("SELECT COUNT(*) FROM valeur_marche").fetchone()[0] == 0:
        mids = [r[0] for r in jeu.execute("SELECT match_id FROM match")]
        print(f"Lecture des valeurs marchandes dans les feuilles de match ({len(mids)} matchs)...")
        n = I.importer_valeurs(jeu, mids)
        if n == 0:
            print("Aucune valeur trouvée : le dossier moteur/cache/matches est-il rempli ? Les prix seront estimés d'après l'OVR.")
    # the season barème windows (the cards' OVR and attributes): computed from the FotMob base if missing
    if jeu.execute("SELECT COUNT(*) FROM bareme_journee").fetchone()[0] == 0:
        fot = pathlib.Path(a.fotmob)
        if not fot.exists():
            sys.exit(f"La base du jeu {src} n'a pas de fenêtres de barème et la base FotMob {fot} n'existe pas.\n"
                     f"Récupère la release data-2025-26 (docs/GUIDE_DEBUTANT.md, étape 6), puis relance.")
        print(f"Calcul du barème de saison depuis {fot} (environ 1 min)...")
        I.importer_bareme(sqlite3.connect(fot), jeu, a.saison)
    amorce = BT.parse_plage(a.amorce)
    for t in ("resultat", "composition", "effectif", "transfert", "ligue_privee_membre", "ligue_privee",
              "equipe", "ligue_jeu", "utilisateur", "carte_historique", "carte"):
        jeu.execute(f"DELETE FROM {t}")
    # gameweeks of the seed count as computed (their performances are the seed);
    # the played half is open, its performances stay in the base for the admin close
    jeu.execute("UPDATE journee SET calculee=1 WHERE saison=? AND numero<=?", (a.saison, amorce[-1]))
    jeu.execute("UPDATE journee SET calculee=0, cloture='2099-01-01T00:00:00Z' WHERE saison=? AND numero>?", (a.saison, amorce[-1]))
    jeu.commit()
    n, params = P.amorcer(jeu, a.saison, a.saison, (amorce[0], amorce[-1]), numero_etat=amorce[-1])
    jeu.execute("VACUUM")
    jeu.commit()
    print(f"{dst}: {n} cartes amorcées sur J{amorce[0]}-J{amorce[-1]} ({params['reguliers']} réguliers) ; "
          f"marché ouvert à J{amorce[-1] + 1}")


if __name__ == "__main__":
    main()
