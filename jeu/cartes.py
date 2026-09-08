"""cartes.py — render player cards from the game base.

    python3 -m jeu.cartes --journee 34 --n 8                 # top 8 of a gameweek
    python3 -m jeu.cartes --joueur 1077894 --journee 34      # one player, one gameweek
    python3 -m jeu.cartes --joueur 1077894                   # season card (OVR + season attributes)

Two kinds of card, both drawn by moteur/carte_design.carte():

  match    the note and six attributes of ONE performance — what the
           tops/flops visuals show;
  saison   the card as the game trades it: OVR in the token, attributes =
           minutes-weighted mean of the season's per-match attributes.

Portraits come from moteur/images/joueurs/{player_id}.png (fetch them with
donnees/portraits.py); without one the card shows the player's initials.
Club colours come from `club.couleur` (importer_couleurs), league decor
from the match's competition.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "moteur"
sys.path.insert(0, str(MOTEUR))

import carte_design as CD  # noqa: E402

from jeu import evolution as E  # noqa: E402
from jeu import notation as N  # noqa: E402

SORTIE = RACINE / "out" / "cartes"
POSTE_COURT = {
    "Gardien": "Gardien", "Defenseur central": "Défenseur", "Lateral": "Latéral",
    "Milieu defensif": "Milieu défensif", "Milieu relayeur": "Milieu",
    "Milieu offensif": "Meneur", "Ailier": "Ailier", "Ailier droit": "Ailier",
    "Ailier gauche": "Ailier", "Buteur": "Buteur",
}


def _journee_id(jeu, numero: int) -> int:
    row = jeu.execute("SELECT journee_id FROM journee WHERE numero=?", (numero,)).fetchone()
    if not row:
        raise SystemExit(f"journée {numero} absente de la base")
    return row[0]


def prestation_carte(jeu: sqlite3.Connection, pid: int, journee: int) -> dict | None:
    """The player's best-rated performance of the gameweek, ready to draw."""
    row = jeu.execute("""
        SELECT p.note, p.attributs, p.poste, p.minutes, c.nom, j.nom, cl.couleur, cl.team_id
        FROM prestation p
        JOIN match m ON m.match_id = p.match_id
        JOIN competition c ON c.competition_id = m.competition_id
        JOIN joueur j ON j.player_id = p.player_id
        LEFT JOIN club cl ON cl.team_id = p.team_id
        WHERE p.player_id = ? AND m.journee_id = ? AND p.note IS NOT NULL
        ORDER BY p.note DESC LIMIT 1""", (pid, _journee_id(jeu, journee))).fetchone()
    if not row:
        return None
    note, attrs, poste, minutes, comp, nom, couleur, tid = row
    return dict(pid=pid, nom=nom, note=note, attributs=json.loads(attrs), poste=poste,
                minutes=minutes, competition=comp, couleur=couleur or "#14161E", team_id=tid)


def carte_saison(jeu: sqlite3.Connection, pid: int, jusqua: int | None = None) -> dict | None:
    """OVR and season attributes (minutes-weighted mean of per-match ones)."""
    cond, args = "", [pid]
    if jusqua is not None:
        cond, args = "AND j.numero <= ?", [pid, jusqua]
    rows = jeu.execute(f"""
        SELECT p.note, p.minutes, p.attributs, p.poste, c.nom
        FROM prestation p JOIN match m ON m.match_id = p.match_id
        JOIN journee j ON j.journee_id = m.journee_id
        JOIN competition c ON c.competition_id = m.competition_id
        WHERE p.player_id = ? AND p.note IS NOT NULL {cond}""", args).fetchall()
    if not rows:
        return None
    hist = [(n, m) for n, m, *_ in rows]
    ovr = E.ovr_initial(hist)
    poids = sum(m for _, m in hist) or 1.0
    somme: dict[str, float] = {}
    for _, m, attrs, *_ in rows:
        for k, v in json.loads(attrs).items():
            somme[k] = somme.get(k, 0.0) + v * m
    attributs = {k: int(round(v / poids)) for k, v in somme.items()}
    from collections import Counter
    poste = Counter(p for *_, p, _c in rows).most_common(1)[0][0]
    comp = Counter(c for *_, c in rows).most_common(1)[0][0]
    nom, couleur, tid = jeu.execute("""
        SELECT j.nom, COALESCE(cl.couleur, '#14161E'), j.team_id
        FROM joueur j LEFT JOIN club cl ON cl.team_id = j.team_id WHERE j.player_id=?""",
        (pid,)).fetchone()
    return dict(pid=pid, nom=nom, note=ovr, ovr=ovr, attributs=attributs, poste=poste,
                minutes=None, competition=comp, couleur=couleur, team_id=tid)


def _jeton_entier(im, cx, cy, note, r, _orig=CD.jeton):
    """Season cards carry an integer OVR in the token, match cards a x.x note."""
    if isinstance(note, int):
        d = CD.ImageDraw.Draw(im)
        _orig(im, cx, cy, 0.0, r)                       # draws the hexagon
        d = CD.ImageDraw.Draw(im)
        d.polygon(CD.hexagone((cx, cy), r - 8), fill=(12, 13, 18, 255))
        d.text((cx, cy + r * 0.05), str(note), font=CD.F('anton', int(r * 1.3)),
               fill=CD.BLANC, anchor='mm')
        return
    _orig(im, cx, cy, note, r)


CD.jeton = _jeton_entier


def dessiner(d: dict, larg: int = 420):
    return CD.carte(d["pid"], d["nom"], d["note"], d["couleur"], d["competition"],
                    POSTE_COURT.get(d["poste"], d["poste"]), d["minutes"], d["attributs"],
                    larg, d["team_id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--journee", type=int, default=None)
    ap.add_argument("--joueur", type=int, nargs="*", default=None)
    ap.add_argument("--n", type=int, default=6, help="top n of the gameweek when no --joueur")
    ap.add_argument("--sortie", default=str(SORTIE))
    ap.add_argument("--larg", type=int, default=420)
    a = ap.parse_args()
    jeu = sqlite3.connect(a.jeu)
    sortie = pathlib.Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    cibles = []
    if a.joueur:
        cibles = a.joueur
    elif a.journee:
        cibles = [r[0] for r in jeu.execute("""
            SELECT p.player_id FROM prestation p JOIN match m ON m.match_id = p.match_id
            WHERE m.journee_id = ? AND p.note IS NOT NULL
            ORDER BY p.note DESC, p.points DESC LIMIT ?""", (_journee_id(jeu, a.journee), a.n))]
    for pid in cibles:
        d = prestation_carte(jeu, pid, a.journee) if a.journee else carte_saison(jeu, pid)
        if d is None:
            print(f"{pid}: rien à dessiner")
            continue
        suffixe = f"J{a.journee}" if a.journee else "saison"
        chemin = sortie / f"{pid}_{suffixe}.png"
        dessiner(d, a.larg).save(chemin)
        print(f"{chemin.name:<24} {d['nom']:<24} {d['poste']:<18} {d['note']} {d['attributs']}")


if __name__ == "__main__":
    main()
