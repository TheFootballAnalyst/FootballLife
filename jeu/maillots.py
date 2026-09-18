"""Les maillots : la couleur et le motif de chaque club, pour que le
terrain ressemble à du football.  `maillot_de(nom)` donne le maillot
domicile ; `tenues(nom_a, nom_b)` donne les deux tenues d'un match, le
visiteur passant en tenue extérieure quand les couleurs se confondent,
et les deux gardiens dans une couleur que personne d'autre ne porte.

Les motifs : uni, bande (une bande verticale au milieu, le PSG), rayures
(verticales, Barcelone), cercle (horizontales, le Sporting), moitie
(deux moitiés, Genoa), echarpe (une diagonale, le Rayo)."""
from __future__ import annotations

import colorsys
import hashlib

# nom en base -> (base, second, motif)
MAILLOTS: dict[str, tuple[str, str, str]] = {
    # France
    "Paris Saint-Germain": ("#1b3d8f", "#d21f2b", "bande"), "Marseille": ("#ffffff", "#2faee0", "uni"),
    "Lyon": ("#ffffff", "#1c3c8c", "uni"), "Monaco": ("#e2231a", "#ffffff", "moitie"), "Lille": ("#d21f2b", "#ffffff", "uni"),
    "Nice": ("#d21f2b", "#111111", "rayures"), "Lens": ("#f5c400", "#c8102e", "rayures"), "Rennes": ("#d21f2b", "#111111", "uni"),
    "Nantes": ("#f6d200", "#0f7a3a", "uni"), "Strasbourg": ("#2a6fd6", "#ffffff", "uni"), "Toulouse": ("#5a2d82", "#ffffff", "uni"),
    "Metz": ("#7a1032", "#ffffff", "uni"), "Le Havre": ("#7fc4ec", "#0b2a5a", "uni"), "Lorient": ("#ff6a13", "#111111", "uni"),
    "Paris FC": ("#0b2a5a", "#ffffff", "uni"), "Angers": ("#111111", "#ffffff", "rayures"), "Auxerre": ("#ffffff", "#1c3c8c", "uni"),
    "Brest": ("#d21f2b", "#ffffff", "uni"),
    # Angleterre
    "Arsenal": ("#ef0107", "#ffffff", "uni"), "Aston Villa": ("#670e36", "#95bfe5", "uni"), "AFC Bournemouth": ("#d21f2b", "#111111", "rayures"),
    "Brentford": ("#d21f2b", "#ffffff", "rayures"), "Brighton & Hove Albion": ("#0057b8", "#ffffff", "rayures"), "Burnley": ("#6c1d45", "#99d6ea", "uni"),
    "Chelsea": ("#034694", "#ffffff", "uni"), "Crystal Palace": ("#c4122e", "#1b458f", "rayures"), "Everton": ("#003399", "#ffffff", "uni"),
    "Fulham": ("#ffffff", "#111111", "uni"), "Leeds United": ("#ffffff", "#ffcd00", "uni"), "Liverpool": ("#c8102e", "#ffffff", "uni"),
    "Manchester City": ("#6cabdd", "#ffffff", "uni"), "Manchester United": ("#da291c", "#ffffff", "uni"), "Newcastle United": ("#111111", "#ffffff", "rayures"),
    "Nottingham Forest": ("#dd0000", "#ffffff", "uni"), "Sunderland": ("#eb172b", "#ffffff", "rayures"), "Tottenham Hotspur": ("#ffffff", "#132257", "uni"),
    "West Ham United": ("#7a263a", "#1bb1e7", "uni"), "Wolverhampton Wanderers": ("#fdb913", "#231f20", "uni"),
    # Espagne
    "Athletic Club": ("#ee2523", "#ffffff", "rayures"), "Atletico Madrid": ("#cb3524", "#ffffff", "rayures"), "Barcelona": ("#a50044", "#004d98", "rayures"),
    "Celta Vigo": ("#8ac3ee", "#ffffff", "uni"), "Deportivo Alaves": ("#0761af", "#ffffff", "rayures"), "Elche": ("#ffffff", "#0f7a3a", "uni"),
    "Espanyol": ("#007fc8", "#ffffff", "rayures"), "Getafe": ("#005999", "#ffffff", "uni"), "Girona": ("#cd2534", "#ffffff", "rayures"),
    "Levante": ("#7a1032", "#1c3c8c", "rayures"), "Mallorca": ("#e2231a", "#111111", "uni"), "Osasuna": ("#d91a21", "#0a1f4e", "uni"),
    "Rayo Vallecano": ("#ffffff", "#e53027", "echarpe"), "Real Betis": ("#00954c", "#ffffff", "rayures"), "Real Madrid": ("#ffffff", "#1c3c8c", "uni"),
    "Real Oviedo": ("#0058a6", "#ffffff", "uni"), "Real Sociedad": ("#0067b1", "#ffffff", "rayures"), "Sevilla": ("#ffffff", "#d81e05", "uni"),
    "Valencia": ("#ffffff", "#111111", "uni"), "Villarreal": ("#ffe667", "#1c3c8c", "uni"),
    # Italie
    "Atalanta": ("#1e71b8", "#111111", "rayures"), "Bologna": ("#a21c26", "#1a2f4e", "rayures"), "Cagliari": ("#b01e2a", "#0b2a5a", "moitie"),
    "Como": ("#1b5fb0", "#ffffff", "uni"), "Cremonese": ("#8c8c8c", "#b01e2a", "rayures"), "Fiorentina": ("#5c2d91", "#ffffff", "uni"),
    "Genoa": ("#b01e2a", "#0b2a5a", "moitie"), "Hellas Verona": ("#1c3c8c", "#ffd500", "uni"), "Inter": ("#0068a8", "#111111", "rayures"),
    "Juventus": ("#111111", "#ffffff", "rayures"), "Lazio": ("#87d8f7", "#ffffff", "uni"), "Lecce": ("#f6d200", "#d21f2b", "rayures"),
    "Milan": ("#fb090b", "#111111", "rayures"), "Napoli": ("#12a0d7", "#ffffff", "uni"), "Parma": ("#ffffff", "#f6d200", "uni"),
    "Pisa": ("#111111", "#1e71b8", "rayures"), "Roma": ("#8e1b1e", "#f0bc42", "uni"), "Sassuolo": ("#00a752", "#111111", "rayures"),
    "Torino": ("#8a1538", "#ffffff", "uni"), "Udinese": ("#111111", "#ffffff", "rayures"),
    # Allemagne
    "Augsburg": ("#ffffff", "#ba3733", "uni"), "Bayer Leverkusen": ("#e32221", "#111111", "uni"), "Bayern München": ("#dc052d", "#ffffff", "uni"),
    "Borussia Dortmund": ("#fde100", "#111111", "uni"), "Borussia Mönchengladbach": ("#ffffff", "#0f7a3a", "uni"), "Eintracht Frankfurt": ("#111111", "#e1000f", "uni"),
    "Freiburg": ("#e2001a", "#ffffff", "uni"), "Hamburger SV": ("#ffffff", "#0a5aa6", "uni"), "FC Heidenheim": ("#e2001a", "#1c3c8c", "uni"),
    "Hoffenheim": ("#1c63b7", "#ffffff", "uni"), "1. FC Köln": ("#ffffff", "#ed1c24", "uni"), "RB Leipzig": ("#ffffff", "#dd0741", "uni"),
    "Mainz 05": ("#c3141e", "#ffffff", "uni"), "St. Pauli": ("#5a3a1e", "#ffffff", "uni"), "VfB Stuttgart": ("#ffffff", "#e32219", "uni"),
    "Union Berlin": ("#eb1923", "#ffffff", "uni"), "Werder Bremen": ("#1d9053", "#ffffff", "uni"), "Wolfsburg": ("#65b32e", "#ffffff", "uni"),
    # Pays-Bas
    "Ajax": ("#ffffff", "#d2122e", "bande"), "AZ Alkmaar": ("#d21f2b", "#ffffff", "uni"), "Excelsior": ("#111111", "#d21f2b", "uni"),
    "FC Groningen": ("#0f7a3a", "#ffffff", "uni"), "Heracles": ("#111111", "#ffffff", "rayures"), "Feyenoord": ("#d21f2b", "#ffffff", "moitie"),
    "Fortuna Sittard": ("#f6d200", "#0f7a3a", "uni"), "Go Ahead Eagles": ("#d21f2b", "#f6d200", "uni"), "SC Heerenveen": ("#1c63b7", "#ffffff", "rayures"),
    "NAC Breda": ("#f6d200", "#111111", "uni"), "NEC Nijmegen": ("#d21f2b", "#0f7a3a", "uni"), "PEC Zwolle": ("#1c63b7", "#ffffff", "uni"),
    "PSV Eindhoven": ("#d21f2b", "#ffffff", "rayures"), "Sparta Rotterdam": ("#d21f2b", "#ffffff", "rayures"), "Telstar": ("#ffffff", "#d21f2b", "uni"),
    "FC Twente": ("#d21f2b", "#ffffff", "uni"), "FC Utrecht": ("#ffffff", "#d21f2b", "uni"), "FC Volendam": ("#ff6a13", "#111111", "uni"),
    # Portugal
    "Alverca": ("#d21f2b", "#ffffff", "uni"), "Arouca": ("#f6d200", "#1c3c8c", "uni"), "AVS Futebol SAD": ("#ffffff", "#1c3c8c", "uni"),
    "Benfica": ("#e30613", "#ffffff", "uni"), "Braga": ("#d21f2b", "#ffffff", "uni"), "Casa Pia AC": ("#111111", "#ffffff", "uni"),
    "Estoril": ("#f6d200", "#1c3c8c", "uni"), "Estrela da Amadora": ("#d21f2b", "#0f7a3a", "rayures"), "Famalicao": ("#1c63b7", "#ffffff", "uni"),
    "Gil Vicente": ("#d21f2b", "#1c3c8c", "uni"), "Moreirense": ("#0f7a3a", "#ffffff", "rayures"), "Nacional": ("#111111", "#ffffff", "rayures"),
    "FC Porto": ("#1c63b7", "#ffffff", "rayures"), "Rio Ave": ("#0f7a3a", "#ffffff", "uni"), "Santa Clara": ("#d21f2b", "#ffffff", "uni"),
    "Sporting CP": ("#0f7a3a", "#ffffff", "cercle"), "Tondela": ("#0f7a3a", "#f6d200", "uni"), "Vitoria de Guimaraes": ("#ffffff", "#111111", "uni"),
    # Turquie
    "Alanyaspor": ("#ff6a13", "#0f7a3a", "uni"), "Antalyaspor": ("#d21f2b", "#ffffff", "uni"), "Başakşehir": ("#ff6a13", "#0b2a5a", "uni"),
    "Beşiktaş": ("#111111", "#ffffff", "rayures"), "Eyüpspor": ("#5c2d91", "#f6d200", "uni"), "Fatih Karagümrük": ("#d21f2b", "#111111", "rayures"),
    "Fenerbahçe": ("#f6d200", "#0b2a5a", "rayures"), "Galatasaray": ("#e2231a", "#f6c400", "moitie"), "Gaziantep FK": ("#d21f2b", "#111111", "uni"),
    "Gençlerbirliği": ("#d21f2b", "#111111", "uni"), "Göztepe": ("#f6d200", "#d21f2b", "moitie"), "Kasımpaşa": ("#0b2a5a", "#ffffff", "uni"),
    "Kayserispor": ("#f6d200", "#d21f2b", "uni"), "Kocaelispor": ("#0f7a3a", "#111111", "uni"), "Konyaspor": ("#0f7a3a", "#ffffff", "cercle"),
    "Rizespor": ("#0f7a3a", "#1c63b7", "uni"), "Samsunspor": ("#d21f2b", "#ffffff", "uni"), "Trabzonspor": ("#7a1032", "#1c63b7", "rayures"),
}
EXTERIEURS = ("#f5f5f5", "#1a1a1a")           # la tenue de rechange : blanche, ou noire si l'autre est claire
GARDIENS = ("#f2d33a", "#3ec46d", "#ff7f27", "#8e44ad", "#00bcd4")


def _rgb(c: str) -> tuple[float, float, float]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _ecart(a: str, b: str) -> float:
    """0 identiques, 1 opposées : une distance de couleur qui compte la
    teinte quand les deux sont saturées, la clarté sinon."""
    ra, rb = _rgb(a), _rgb(b)
    ha, sa, va = colorsys.rgb_to_hsv(*ra)
    hb, sb, vb = colorsys.rgb_to_hsv(*rb)
    dv = abs(va - vb)
    if sa < 0.25 or sb < 0.25:                 # l'une est blanche/grise/noire : la clarté décide
        return max(dv, abs(sa - sb) * 0.6)
    dh = min(abs(ha - hb), 1 - abs(ha - hb)) * 2   # 0..1
    return max(dh, dv * 0.8)


def maillot_de(nom: str) -> dict:
    m = MAILLOTS.get(nom)
    if m is None:
        # un club sans maillot connu : une couleur stable tirée de son nom
        h = int(hashlib.md5(nom.encode("utf-8")).hexdigest(), 16) % 360
        r, g, b = colorsys.hsv_to_rgb(h / 360.0, 0.75, 0.75)
        m = ("#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255)), "#ffffff", "uni")
    return {"base": m[0], "second": m[1], "motif": m[2]}


def _dominante(m: dict) -> str:
    return m["base"]


def tenues(nom_a: str, nom_b: str) -> dict:
    """Les deux tenues et les deux gardiens d'un match."""
    a, b = maillot_de(nom_a), maillot_de(nom_b)
    if _ecart(a["base"], b["base"]) < 0.35 or (a["motif"] != "uni" and b["motif"] != "uni" and _ecart(a["second"], b["second"]) < 0.3
                                                and _ecart(a["base"], b["base"]) < 0.5):
        # le visiteur change : blanc, ou noir si l'hôte est clair
        ext = EXTERIEURS[1] if _ecart(a["base"], EXTERIEURS[0]) < 0.35 else EXTERIEURS[0]
        b = {"base": ext, "second": b["base"], "motif": "uni"}
    pris = [a["base"], b["base"], a["second"], b["second"]]
    gk = []
    for cand in GARDIENS:
        if all(_ecart(cand, c) >= 0.35 for c in pris + gk):
            gk.append(cand)
        if len(gk) == 2:
            break
    while len(gk) < 2:
        gk.append(GARDIENS[len(gk)])
    return {"a": a, "b": b, "gardiens": gk}
