#!/usr/bin/env python3
"""saison.py — la saison en cours, du fournisseur à la base du jeu.

    py outils/saison.py construire --saison 2026/27     # une base neuve : les matchs depuis le 1er août, l'amorce depuis
                                                        # 2025/26 (barème Ballon d'or + palmarès), les journées rejouées jusqu'à hier
    py outils/saison.py semaine --saison 2026/27        # chaque semaine : les nouveaux matchs, les journées terminées calculées
    py outils/saison.py semaine --saison 2026/27 --exporter   # pour un site en ligne : écrit out/journees/*.json au lieu de calculer ici
    py outils/saison.py mouvements --saison 2026/27     # les cartes qui ont le plus bougé depuis l'amorce
    py outils/saison.py etat --saison 2026/27

Tout est déduit de la saison : la base du moteur moteur/fotmob_2627.db,
la base du jeu jeu/jeu_2627.sqlite, la saison source 2025/26 et sa base
moteur/fotmob_2526.db (release data-2025-26). La prod (jeu/demo.sqlite)
n'est pas touchée : la base de la saison se joue à part
(`py outils/environnements.py lancer 2627`, port 8004), et devient la prod
le jour où on le décide, en la copiant.

Ce que « construire » fait, dans l'ordre : donnees/journee.py récupère et
ingère les matchs ; jeu/importer.py note chaque prestation et calcule le
barème de saison par journée ; les journées sont créées depuis les tours
de Ligue 1 ; jeu/pipeline.amorcer fixe les cartes au Ballon d'or de la
saison source ; puis chaque journée dont la fenêtre est passée est
calculée comme elle l'aurait été à la semaine : transferts
(rafraichir_clubs), nouveaux venus (integrer_nouveaux), évolution des
cartes bornée. Rien n'est inventé : la note d'aujourd'hui est celle que
le jeu aurait donnée en jouant la saison depuis août.

À lancer depuis une machine qui atteint fotmob.com. Compter dix minutes
pour la récupération d'août à octobre, puis trois ou quatre pour le reste.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from datetime import date, timedelta

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from donnees import journee as J  # noqa: E402
from jeu import importer as I  # noqa: E402
from jeu import pipeline as P  # noqa: E402

LIGUE_REFERENCE = 53          # les journées suivent les tours de Ligue 1
PORT = 8004


def saison_precedente(saison: str) -> str:
    a = int(saison.split("/")[0])
    return f"{a - 1}/{a % 100:02d}"


def chemins(saison: str) -> dict:
    a, b = saison.split("/")
    court = f"{a[-2:]}{b[-2:]}"
    return dict(fotmob=J.base_de_saison(saison), jeu=RACINE / "jeu" / f"jeu_{court}.sqlite",
                source=saison_precedente(saison), fotmob_source=J.base_de_saison(saison_precedente(saison)),
                cache=J.CACHE, sortie=RACINE / "out" / "journees")


def debut(saison: str) -> date:
    """Le 1er août : les supercoupes d'ouverture sont dedans."""
    return date(int(saison.split("/")[0]), 8, 1)


def aujourdhui() -> date:
    return date.today()


def court(p: pathlib.Path) -> str:
    """Le chemin relatif au dépôt quand il y est."""
    try:
        return str(pathlib.Path(p).relative_to(RACINE))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------
# Les journées
# --------------------------------------------------------------------------

def journees_terminees(jeu, saison: str, jour: date) -> list[int]:
    """Les journées pas encore calculées dont la fenêtre est passée au
    matin de `jour` (au < jour), dans l'ordre."""
    return [n for n, in jeu.execute("""SELECT numero FROM journee WHERE saison=? AND numero >= 1
                                        AND calculee = 0 AND au < ? ORDER BY numero""",
                                    (saison, jour.isoformat()))]


def rejouer(jeu, fot, saison: str, jour: date, journal=print) -> list[dict]:
    """Calculer, dans l'ordre, chaque journée terminée : avec `fot` les
    prestations sont (ré)importées de la base du moteur, sans elle celles
    déjà dans la base du jeu servent."""
    faits = []
    for n in journees_terminees(jeu, saison, jour):
        r = P.calculer(jeu, fot, saison, n, importer=fot is not None)
        faits.append(r)
        journal(f"  J{n:>2}  {r['du']} → {r['au']}  {r.get('prestations', '-'):>5} prestations, "
                f"{r['cartes_bougees']} cartes bougées, {r['nouvelles_cartes']} nouvelles, {r['clubs_maj']} changements de club")
    return faits


def mouvements(jeu, saison: str, depuis: int = 0, n: int = 10) -> dict:
    """Les cartes qui ont le plus monté et le plus baissé entre l'état
    après la journée `depuis` et la dernière journée calculée."""
    derniere = jeu.execute("SELECT MAX(numero) FROM journee WHERE saison=? AND calculee=1", (saison,)).fetchone()[0]
    if derniere is None or derniere <= depuis:
        return dict(depuis=depuis, jusqua=derniere, hausses=[], baisses=[], cartes=0)
    j0, j1 = P.journee_id(jeu, saison, depuis), P.journee_id(jeu, saison, derniere)
    rows = jeu.execute("""
        SELECT jo.nom, COALESCE(c.nom, '-'), jo.poste, h0.ovr, h1.ovr, h1.ovr - h0.ovr
        FROM carte_historique h1 JOIN carte_historique h0 ON h0.player_id = h1.player_id AND h0.journee_id = ?
        JOIN joueur jo ON jo.player_id = h1.player_id LEFT JOIN club c ON c.team_id = jo.team_id
        WHERE h1.journee_id = ?""", (j0, j1)).fetchall()
    rows.sort(key=lambda r: (-r[5], r[0]))
    return dict(depuis=depuis, jusqua=derniere, cartes=len(rows),
                hausses=[r for r in rows[:n] if r[5] > 0], baisses=[r for r in sorted(rows, key=lambda r: (r[5], r[0]))[:n] if r[5] < 0])


def afficher_mouvements(m: dict, journal=print):
    if not m["cartes"]:
        journal("  (aucune journée calculée après l'amorce)")
        return
    journal(f"  {m['cartes']} cartes, de l'état J{m['depuis']} à J{m['jusqua']}")
    for titre, rows in (("en hausse", m["hausses"]), ("en baisse", m["baisses"])):
        journal(f"  {titre} :")
        for nom, club, poste, o0, o1, d in rows:
            journal(f"    {d:+3d}  {o0:>2} → {o1:>2}  {nom} ({club}, {poste})")


# --------------------------------------------------------------------------
# Construire, puis chaque semaine
# --------------------------------------------------------------------------

def construire(saison: str, depuis: date | None = None, jusqua: date | None = None, telecharger: bool = True,
               entetes: dict | None = None, ecraser: bool = False, fotmob_source: pathlib.Path | None = None,
               journal=print) -> dict:
    ch = chemins(saison)
    source = pathlib.Path(fotmob_source) if fotmob_source else ch["fotmob_source"]
    jusqua = jusqua or aujourdhui()
    depuis = depuis or debut(saison)
    if ch["jeu"].exists() and not ecraser:
        sys.exit(f"{ch['jeu']} existe déjà : `semaine` pour la continuer, --ecraser pour la refaire (ses comptes et équipes seront perdus)")
    if not source.exists():
        sys.exit(f"la base FotMob de la saison source manque : {source} (release data-2025-26, docs/GUIDE_DEBUTANT.md étape 6)")
    noms = J.noms_de_reference(source)
    if telecharger:
        journal(f"1. Les matchs du {depuis} au {jusqua}, vers {ch['fotmob']}")
        bilan = J.recuperer(depuis, jusqua, ch["fotmob"], ch["cache"], entetes, noms=noms, journal=journal)
        journal(J.resume(bilan))
    elif not ch["fotmob"].exists():
        sys.exit(f"{ch['fotmob']} n'existe pas : sans --sans-telechargement, elle est construite depuis FotMob")
    else:
        J.finaliser(sqlite3.connect(ch["fotmob"]), noms)
    for suffixe in ("", "-wal", "-shm"):
        p = pathlib.Path(str(ch["jeu"]) + suffixe)
        if p.exists():
            p.unlink()
    journal(f"2. Les prestations notées et le barème de saison, vers {ch['jeu']}")
    I.main_import(ch["fotmob"], ch["jeu"], saison, ligue=LIGUE_REFERENCE)
    jeu = I.ouvrir_jeu(ch["jeu"])
    fot = sqlite3.connect(ch["fotmob"])
    mids = [r[0] for r in jeu.execute("SELECT match_id FROM match")]
    journal(f"   valeurs marchandes lues dans les feuilles : {I.importer_valeurs(jeu, mids, ch['cache'])}")
    P.creer_journees(jeu, fot, saison, LIGUE_REFERENCE)
    jeu.execute("UPDATE journee SET calculee=0 WHERE saison=? AND numero >= 1", (saison,))
    jeu.commit()
    journal(f"3. L'amorce : le Ballon d'or {ch['source']} depuis {source} (environ une minute)")
    n, params = P.amorcer(jeu, saison, ch["source"], fot=sqlite3.connect(source))
    journal(f"   {n} cartes, panel {params['panel']}, réguliers {params['reguliers']}, palmarès pour {params['source']['palmares']} joueurs")
    journal(f"4. Les journées terminées, rejouées jusqu'au {jusqua}")
    faits = rejouer(jeu, None, saison, jusqua, journal)
    if not faits:
        journal("   aucune journée terminée pour l'instant")
    jeu.execute("VACUUM")
    jeu.commit()
    m = mouvements(jeu, saison)
    afficher_mouvements(m, journal)
    journal(f"\nFait : {ch['jeu']}. Ensuite, sur ta machine :\n"
            f"  py donnees/portraits.py --jeu {court(ch['jeu'])}   # les portraits des nouveaux venus\n"
            f"  py donnees/pieds.py --jeu {court(ch['jeu'])}       # leur pied fort, puis py -m jeu.importer --jeu … --physique-seulement\n"
            f"  py outils/environnements.py lancer {saison.replace('/', '')[-4:]}   # http://localhost:{PORT}\n"
            f"  py outils/saison.py semaine --saison {saison}        # chaque semaine")
    return dict(cartes=n, journees=[r["journee"] for r in faits], mouvements=m)


def semaine(saison: str, exporter: bool = False, telecharger: bool = True, entetes: dict | None = None,
            jour: date | None = None, journal=print) -> dict:
    ch = chemins(saison)
    jour = jour or aujourdhui()
    if not ch["jeu"].exists():
        sys.exit(f"{ch['jeu']} n'existe pas : py outils/saison.py construire --saison {saison}")
    jeu = I.ouvrir_jeu(ch["jeu"])
    if telecharger:
        premiere = jeu.execute("SELECT MIN(du) FROM journee WHERE saison=? AND numero>=1 AND calculee=0", (saison,)).fetchone()[0]
        du = min(date.fromisoformat(premiere) if premiere else jour, jour - timedelta(days=10))
        journal(f"1. Les matchs du {du} au {jour}")
        bilan = J.recuperer(du, jour, ch["fotmob"], ch["cache"], entetes, noms=J.noms_de_reference(ch["fotmob_source"]), journal=journal)
        journal(J.resume(bilan))
    elif not ch["fotmob"].exists():
        sys.exit(f"{ch['fotmob']} n'existe pas")
    fot = sqlite3.connect(ch["fotmob"])
    P.creer_journees(jeu, fot, saison, LIGUE_REFERENCE)
    terminees = journees_terminees(jeu, saison, jour)
    if not terminees:
        prochaine = jeu.execute("SELECT numero, au FROM journee WHERE saison=? AND calculee=0 AND numero>=1 ORDER BY numero LIMIT 1",
                                (saison,)).fetchone()
        journal("Aucune journée terminée" + (f" : la J{prochaine[0]} court jusqu'au {prochaine[1]} inclus" if prochaine else ""))
        return dict(journees=[], fichiers=[])
    if exporter:
        from jeu import exporter_journee as X
        ch["sortie"].mkdir(parents=True, exist_ok=True)
        fichiers = []
        for n in terminees:
            doc = X.exporter(fot, jeu, saison, n)
            f = ch["sortie"] / f"{saison.replace('/', '-')}_J{n}.json"
            f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            fichiers.append(f)
            journal(f"  J{n:>2}  {len(doc['prestations'])} prestations → {f}  (Admin → charger les prestations, puis clôturer)")
        return dict(journees=terminees, fichiers=fichiers)
    journal(f"2. Le barème de saison recalculé sur {ch['fotmob']} (environ une minute)")
    I.importer_bareme(fot, jeu, saison)
    mids = [r[0] for r in jeu.execute("SELECT match_id FROM match")]
    I.importer_valeurs(jeu, mids, ch["cache"])
    journal(f"3. Les journées terminées : {', '.join(f'J{n}' for n in terminees)}")
    faits = rejouer(jeu, fot, saison, jour, journal)
    I.importer_pieds(jeu)
    jeu.commit()
    afficher_mouvements(mouvements(jeu, saison, depuis=max(terminees[0] - 1, 0)), journal)
    return dict(journees=[r["journee"] for r in faits], fichiers=[])


def etat(saison: str, journal=print):
    ch = chemins(saison)
    journal(f"base du moteur : {ch['fotmob']} {'ok' if ch['fotmob'].exists() else 'absente'}")
    journal(f"base du jeu    : {ch['jeu']} {'ok' if ch['jeu'].exists() else 'absente'}")
    journal(f"saison source  : {ch['source']}, {ch['fotmob_source']} {'ok' if ch['fotmob_source'].exists() else 'absente'}")
    if not ch["jeu"].exists():
        return
    jeu = I.ouvrir_jeu(ch["jeu"])
    e = P.etat(jeu, saison)
    journal(f"{e['cartes']} cartes ; journées : " + ", ".join(f"J{j['numero']}{'✓' if j['calculee'] else ''}" for j in e["journees"]))
    afficher_mouvements(mouvements(jeu, saison), journal)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")      # une console Windows redirigée n'a pas toujours l'UTF-8
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commande", choices=["construire", "semaine", "mouvements", "etat"])
    ap.add_argument("--saison", default=J.saison_du_jour(date.today()))
    ap.add_argument("--depuis", help="construire : premier jour récupéré (défaut : le 1er août)")
    ap.add_argument("--jusqua", help="dernier jour récupéré et dernière fenêtre considérée (défaut : aujourd'hui)")
    ap.add_argument("--source-fotmob", default=None, help="construire : la base FotMob de la saison source (défaut : moteur/fotmob_AABB.db)")
    ap.add_argument("--sans-telechargement", action="store_true", help="la base du moteur est déjà à jour")
    ap.add_argument("--ecraser", action="store_true", help="construire : refaire une base du jeu qui existe")
    ap.add_argument("--exporter", action="store_true", help="semaine : écrire les journées en JSON pour l'écran Admin au lieu de les calculer ici")
    ap.add_argument("--entete", action="append", default=[], help='en-tête HTTP « Nom: valeur » pour FotMob, gardé dans moteur/entetes.json')
    ap.add_argument("--depuis-journee", type=int, default=0, help="mouvements : l'état de départ (défaut : l'amorce)")
    a = ap.parse_args()
    entetes = J.lire_entetes(a.entete)
    jusqua = date.fromisoformat(a.jusqua) if a.jusqua else None
    if a.commande == "construire":
        construire(a.saison, date.fromisoformat(a.depuis) if a.depuis else None, jusqua, not a.sans_telechargement,
                   entetes, a.ecraser, a.source_fotmob)
    elif a.commande == "semaine":
        semaine(a.saison, a.exporter, not a.sans_telechargement, entetes, jusqua)
    elif a.commande == "mouvements":
        ch = chemins(a.saison)
        if not ch["jeu"].exists():
            sys.exit(f"{ch['jeu']} n'existe pas")
        afficher_mouvements(mouvements(I.ouvrir_jeu(ch["jeu"]), a.saison, a.depuis_journee))
    else:
        etat(a.saison)


if __name__ == "__main__":
    main()
