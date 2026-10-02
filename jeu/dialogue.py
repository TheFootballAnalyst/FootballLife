"""La boîte de dialogue : parler à son équipe pendant le match (PLAN.md § 2.5).

« On presse haut », « les latéraux restent derrière », « Hakimi, reste
derrière », « Dembélé décroche », « marquez Mbappé », « Kolo Muani remplace
Dembélé », « Hakimi et Mendes permutent », « on passe en 4-4-2 », et à la
pause « réveillez-vous ».  Chaque phrase se traduit en un levier QUE LE
MOTEUR A DÉJÀ (la tactique, les consignes par ligne, le marquage, un
changement, une permutation, la causerie), avec une phrase de confirmation
qui dit ce qui va vraiment se passer — une consigne à un joueur vaut pour
sa ligne, et la confirmation le dit.

Pas d'intelligence artificielle en ligne : des règles, un vocabulaire, et
le jeu marche hors ligne.  Le vocabulaire est rangé par langue (`VOCABULAIRE`,
« fr » aujourd'hui) pour le chantier 3 : une autre langue, c'est une autre
table, pas un autre code.

Ce qu'on ne traduit PAS, et qu'on dit : « cherche Dembélé dans l'axe »
(le moteur n'a pas de consigne joueur-vers-joueur), et tout ce qui n'est
pas dans le vocabulaire — la réponse propose alors trois phrases qui
marchent, prises dans la situation du moment.
"""
from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------
# Le vocabulaire, par langue
# --------------------------------------------------------------------------
# Chaque entrée : (motifs, levier) — un motif est une expression régulière sur
# la phrase normalisée (minuscules, sans accents, sans ponctuation).  L'ordre
# compte : le premier motif qui prend l'emporte dans son groupe.

VOCABULAIRE: dict[str, dict] = {
    "fr": {
        # -- l'équipe entière : les trois axes de la tactique --------------------
        "equipe": [
            # le bloc
            (r"\b(presse|pressez|pressing|pressons)\b.*\bhaut\b|\bbloc haut\b|\bon (monte|remonte)\b|\bplus haut\b|\bon presse\b|\bpressez\b|\ballez les chercher\b",
             {"bloc": "haut"}),
            (r"\bbloc bas\b|\bon (recule|se replie|defend bas|reste bas)\b|\bplus bas\b|\breculez\b|\brepliez\b|\bon attend\b|\bbus\b",
             {"bloc": "bas"}),
            (r"\bbloc (median|median|moyen|intermediaire)\b|\bbloc normal\b", {"bloc": "median"}),
            # le tempo
            (r"\b(garde|gardez|gardons|conserve|conservez|conservons)\b.*\bballon\b|\bpossession\b|\bfai(s|tes) tourner\b|\bon fait tourner\b|\bon joue court\b|\bjeu court\b|\bprenez votre temps\b",
             {"tempo": "possession"}),
            (r"\b(joue|jouez|jouons|on joue)\b.*\b(direct|vite|long|rapide)\b|\bjeu direct\b|\bverticali\w*\b|\bvite devant\b|\bdirect\b|\bbalance\w* (devant|long)\b",
             {"tempo": "direct"}),
            (r"\btempo (normal|equilibre)\b|\bjeu (normal|equilibre)\b", {"tempo": "equilibre"}),
            # le risque
            (r"\bon (attaque|attaquons|va chercher|y va)\b|\battaquez\b|\btout le monde devant\b|\boffensif\w*\b|\ballez y\b|\bon pousse\b|\bpoussez\b|\bon ouvre le jeu\b|\bon prend des risques\b",
             {"risque": "offensif"}),
            (r"\bon (ferme|tient|verrouille|garde le resultat|serre|assure)\b|\bfermez\b|\bprudent\w*\b|\bon ferme (la boutique|le jeu)\b|\bpas de risque\w*\b|\bon ne prend pas de risque\w*\b|\btenez le (resultat|score)\b",
             {"risque": "prudent"}),
            (r"\brisque (normal|equilibre)\b|\bon se calme\b.*\bjeu\b", {"risque": "equilibre"}),
        ],
        # -- les lignes : (motif de la ligne, [(motif de l'ordre, valeur)]) ------
        "lignes": {
            "lateraux": (r"\blatera(l|ux)\b|\barriere\w* (lateral|lateraux|droit|gauche)\b",
                         [(r"\b(bas|derriere|reste\w*|montez? (pas|plus)|ne monte\w* (pas|plus)|n y va\w* (pas|plus))\b", "bas"),
                          (r"\b(axe|rentre\w*|interieur|dedans)\b", "axe"),
                          (r"\b(couloir|monte\w*|montez|ligne|large|libre\w*)\b", "couloir")]),
            "ailiers": (r"\bailier\w*\b|\bexcentre\w*\b",
                        [(r"\b(ligne|touche|large\w*|couloir|ecarte\w*|ouvre\w* le jeu)\b", "ligne"),
                         (r"\b(rentre\w*|repique\w*|interieur|axe|dedans|resserre\w*)\b", "interieur"),
                         (r"\b(normal|equilibre|libre\w*)\b", "equilibre")]),
            "milieux": (r"\bmilieu\w*\b|\bentrejeu\b",
                        [(r"\b(projet\w*|monte\w*|montez|rejoi\w*|attaque\w*|devant|accompagne\w*)\b", "projection"),
                         (r"\b(bas|derriere|reste\w*|couvre\w*|protege\w*|sentinelle)\b", "bas"),
                         (r"\b(cote\w*|lateral\w*|large|ecarte\w*|couloir\w*)\b", "lateral"),
                         (r"\b(normal|equilibre|libre\w*)\b", "equilibre")]),
            "attaquants": (r"\battaquant\w*\b|\bavant\w*\b|\bbuteur\w*\b|\bpointe\b",
                           [(r"\b(profondeur|dans le dos|appel\w*|derriere la defense|en profondeur|prend\w* la profondeur)\b", "profondeur"),
                            (r"\b(pivot|dos au but|decroche\w*|remise\w*|point d appui|appui)\b", "pivot"),
                            (r"\b(normal|equilibre|libre\w*)\b", "equilibre")]),
            "relance": (r"\brelance\w*\b|\bressort\w*\b|\brelancez\b|\bgardien\b",
                        [(r"\b(court\w*|par le bas|au sol|propre\w*|a terre|pied\w*)\b", "courte"),
                         (r"\b(long\w*|degage\w*|balance\w*|loin|au loin)\b", "longue"),
                         (r"\b(normal|equilibre|libre\w*)\b", "equilibre")]),
        },
        # -- un joueur de chez nous, nommé : l'ordre vaut pour sa ligne ----------
        # (poste → ligne) : un latéral entend « lateraux », un ailier « ailiers »...
        "joueur": {
            "LB": "lateraux", "RB": "lateraux", "LWB": "lateraux", "RWB": "lateraux",
            "LW": "ailiers", "RW": "ailiers", "LM": "ailiers", "RM": "ailiers",
            "CM": "milieux", "CDM": "milieux", "CAM": "milieux",
            "ST": "attaquants", "CF": "attaquants",
            "GK": "relance", "CB": "relance",
        },
        # -- le marquage : un joueur d'en face ------------------------------------
        "marquage": r"\b(marque\w*|marquage|prend\w*|prends|colle\w*|serre\w*|musel\w*|lache\w* pas|ne lache\w* pas|surveille\w*|bloque\w*|neutralise\w*|a l oeil|ne le lach\w*)\b",
        "demarquage": r"\b(lache\w*|libere\w*|arrete\w*|fin du|plus de|stop)\b.*\bmarquage\b|\bmarquage\b.*\b(fini|termine|stop)\b|\bon lache le marquage\b|\bplus de marquage\b|\barrete\w* le marquage\b",
        # -- un changement, une permutation ---------------------------------------
        "changement": r"\b(remplace\w*|a la place de|pour|entre\w*|sort\w*|rentre\w*|change\w*|fai\w* entrer|fai\w* sortir|a la place d)\b",
        "permutation": r"\b(permute\w*|echange\w*|inverse\w*|intervertis\w*|change\w* de (cote|poste|place)|swap)\b",
        # -- la causerie ------------------------------------------------------------
        "causerie": [
            (r"\b(reveille\w*|secoue\w*|bouge\w*|allez|on se bouge|on se reveille|du nerf|de l envie|on dort|reagissez|reveil|mollesse|on y va)\b", "secouer"),
            (r"\b(calme\w*|sang froid|tranquille\w*|rassure\w*|respire\w*|on ne panique pas|pas de panique|serein\w*|restez concentre\w*|on gere)\b", "rassurer"),
            (r"\b(bravo|bien joue|continue\w*|felicit\w*|super|parfait|excellent|comme ca|fier\w*|chapeau|c est bien)\b", "feliciter"),
            (r"\b(rien|on ne dit rien|pas de causerie|je ne dis rien|silence)\b", "rien"),
        ],
        # -- ce qu'on ne sait pas faire, et qu'on dit ---------------------------------
        "impossible": [
            (r"\bcherche\w*\b.*\b(dans l axe|sur le cote|en profondeur|dans le dos)\b|\bcherche\w*\b", "chercher"),
            (r"\b(tire\w*|frappe\w*) de loin\b|\btirez\b|\bfrappez\b", "tirer"),
            (r"\b(centre\w*|centrez)\b", "centrer"),
        ],
        # -- les phrases de la confirmation ----------------------------------------
        "textes": {
            "bloc": {"haut": "on presse haut", "median": "le bloc revient au médian", "bas": "on se replie en bloc bas"},
            "tempo": {"possession": "on garde le ballon", "equilibre": "le tempo redevient normal", "direct": "on joue direct"},
            "risque": {"offensif": "on attaque", "equilibre": "on rejoue normalement", "prudent": "on ferme le jeu"},
            "lateraux": {"couloir": "les latéraux montent dans leur couloir", "bas": "les latéraux restent derrière",
                         "axe": "les latéraux rentrent dans l'axe"},
            "ailiers": {"equilibre": "les ailiers jouent normalement", "ligne": "les ailiers collent la ligne de touche",
                        "interieur": "les ailiers repiquent dans l'axe"},
            "milieux": {"equilibre": "les milieux jouent normalement", "projection": "les milieux se projettent",
                        "bas": "les milieux restent derrière", "lateral": "les milieux organisent sur les côtés"},
            "attaquants": {"equilibre": "les attaquants jouent normalement", "profondeur": "les attaquants prennent la profondeur",
                           "pivot": "les attaquants jouent en pivot, dos au but"},
            "relance": {"equilibre": "on relance normalement", "courte": "on ressort le ballon par le bas", "longue": "on relance long"},
            "formation": "on passe en {formation}",
            "marquage": "{qui} sera marqué de près",
            "demarquage": "on lâche le marquage",
            "changement": "{entrant} entre à la place de {sortant} au prochain arrêt de jeu",
            "permutation": "{un} et {deux} permutent",
            "causerie": {"secouer": "tu les secoues", "rassurer": "tu les rassures", "feliciter": "tu les félicites",
                         "rien": "tu ne leur dis rien"},
            "joueur": "{nom} et sa ligne : {texte}",
            "chercher": "Le moteur ne sait pas encore demander à un joueur d'en chercher un autre : "
                        "dis-lui plutôt où jouer (« {nom}, rentre dans l'axe », « {nom}, prends la profondeur »).",
            "tirer": "Les tirs, c'est eux qui décident : tu peux leur demander d'attaquer (« on attaque ») ou de jouer direct.",
            "centrer": "Les centres viennent des ailiers qui collent la ligne (« les ailiers restent larges ») et des latéraux qui montent.",
            "incompris": "Je n'ai pas compris. Essaie par exemple : {exemples}.",
            "deja": "C'est déjà ce qu'ils font.",
            "qui": "Je ne sais pas de qui tu parles : {noms}.",
            "banc": "{nom} n'est pas sur ton banc.",
            "terrain": "{nom} n'est pas sur le terrain.",
            "adversaire": "{nom} ne joue pas en face.",
            "permutation_deux": "Pour une permutation il me faut deux joueurs sur le terrain.",
            "pas_mi_temps": "C'est à la mi-temps qu'on parle à son équipe ; là, donne-leur une consigne.",
            "changement_deux": "Pour un changement il me faut un joueur sur le terrain et un sur le banc.",
        },
        # les exemples qu'on propose quand on n'a pas compris (tirés de la situation)
        "exemples": ["on presse haut", "les latéraux restent derrière", "{adv}, marque-le",
                     "{banc} remplace {terrain}", "on passe en 4-4-2", "on garde le ballon"],
    },
}

# -- English: the pivot language (PLAN.md § 3). Same shape as French: patterns on the
# normalised sentence (lower case, no accents, no punctuation), one lever per match.
VOCABULAIRE["en"] = {
    "equipe": [
        (r"\b(press(es|ing)?|push up|go and get them|get after them|high (block|line|press)|higher|squeeze)\b", {"bloc": "haut"}),
        (r"\b(sit (back|deep|deeper)|drop (back|deep|deeper|off)|low block|deeper|park the bus|stay compact|fall back)\b", {"bloc": "bas"}),
        (r"\b(mid|middle|normal) block\b|\bmedium block\b", {"bloc": "median"}),
        (r"\b(keep (the )?ball|possession|keep it(?! (up|going))|pass it around|take (your|our) time|slow it down|patient)\b", {"tempo": "possession"}),
        (r"\b(play (it )?(direct|quick|quicker|fast|faster|long)|direct|go long|long ball|verticali\w*|quickly forward|hit them early)\b", {"tempo": "direct"}),
        (r"\b(normal|balanced) tempo\b", {"tempo": "equilibre"}),
        (r"\b(attack|all out|everyone forward|go for it|push for (a|the) (goal|winner)|open (it|the game) up|take risks|be bold|offensive)\b", {"risque": "offensif"}),
        (r"\b(close (it|the game) (down|up|out)|shut (it|up) shop|hold (on|the result|the score|the lead)|see it out|no risks?|careful|cautious|tighten up|sit on (it|the lead))\b", {"risque": "prudent"}),
        (r"\b(normal|balanced) (risk|game)\b", {"risque": "equilibre"}),
    ],
    "lignes": {
        "lateraux": (r"\b(full ?backs?|wing ?backs?|right back|left back)\b",
                     [(r"\b(stay (back|home|deep)|hold|do(n t| not) (go|push|overlap)|no overlap\w*|sit)\b", "bas"),
                      (r"\b(inside|tuck|invert\w*|narrow|into the middle|in the middle)\b", "axe"),
                      (r"\b(overlap\w*|push (up|on|forward)|get forward|bomb on|wide|free|flank|wing)\b", "couloir")]),
        "ailiers": (r"\b(wingers?|wide (men|players?|forwards?))\b",
                    [(r"\b(stay wide|wide|touchline|hug|stretch|width|chalk)\b", "ligne"),
                     (r"\b(cut (in|inside)|come (in|inside|narrow)|inside|narrow|invert\w*|tuck)\b", "interieur"),
                     (r"\b(normal|balanced|free)\b", "equilibre")]),
        "milieux": (r"\b(midfield\w*|middle of the park|engine room)\b",
                    [(r"\b(get forward|push (up|on|forward)|join (the )?attack|burst|late runs?|into the box|support the attack)\b", "projection"),
                     (r"\b(sit|stay (back|deep)|hold|protect|shield|screen|cover)\b", "bas"),
                     (r"\b(wide|out wide|to the wings?|flanks?|spread (it|the play))\b", "lateral"),
                     (r"\b(normal|balanced|free)\b", "equilibre")]),
        "attaquants": (r"\b(strikers?|forwards?|front ?(men|line|two|three)|number nine|attackers?)\b",
                       [(r"\b(in behind|run\w* (in behind|behind|deep)|depth|stretch|over the top|get in behind)\b", "profondeur"),
                        (r"\b(hold (it|the ball) up|hold up|target man|back to goal|drop (deep|off|in)|link|lay ?offs?|come short)\b", "pivot"),
                        (r"\b(normal|balanced|free)\b", "equilibre")]),
        "relance": (r"\b(build ?up|play out|from the back|goal ?kicks?|keeper|goalkeeper|distribution)\b",
                    [(r"\b(short|on the ground|from the back|play out|through the lines|feet)\b", "courte"),
                     (r"\b(long|clear|launch|kick it long|go long|over the top|skip the midfield)\b", "longue"),
                     (r"\b(normal|balanced|free)\b", "equilibre")]),
    },
    "joueur": VOCABULAIRE["fr"]["joueur"],
    "marquage": r"\b(mark\w*|man ?mark\w*|stick (to|on|with)|tight on|pick up|track|follow|shadow|stay (on|with)|do(n t| not) (let|leave)|watch|keep an eye|neutrali\w*|nullif\w*|close down|get tight)\b",
    "demarquage": r"\b(drop|stop|end|no more|forget|release|lift|cancel|off)\b.*\b(mark\w*)\b|\b(mark\w*)\b.*\b(off|over|done)\b|\bno (more )?mark\w*\b|\bzonal\b",
    "changement": r"\b(replace\w*|for|instead of|in place of|comes? (on|in|off)|bring (on|in|off)|sub\w*|take (off|out)|swap in|on for|off for|goes off|come off|hook)\b",
    "permutation": r"\b(swap|switch|swop|exchange|interchange|change (sides?|flanks?|positions?|wings?)|rotate)\b",
    "causerie": [
        (r"\b(wake up|shake|come on|wake|move|get going|more (energy|effort|intensity)|not good enough|sleeping|asleep|pick it up|step it up|get into them|let s go|fire up)\b", "secouer"),
        (r"\b(calm|relax|composure|composed|settle|breathe|no panic|do(n t| not) panic|keep (your|our) heads?|stay (calm|focused|composed)|easy|steady|patient)\b", "rassurer"),
        (r"\b(well done|good job|great|brilliant|superb|excellent|keep (it|this) (up|going)|proud|more of the same|fantastic|perfect|nice|lovely|that s it)\b", "feliciter"),
        (r"\b(nothing|say nothing|no talk|silence|leave (them|it))\b", "rien"),
    ],
    "impossible": [
        (r"\b(look for|find|feed|pass to|play (in|to)|link (up )?with|give it to|target)\b", "chercher"),
        (r"\b(shoot\w*|shots?|have a go|from distance|long range|take a shot)\b", "tirer"),
        (r"\b(cross\w*|deliver\w*|whip)\b", "centrer"),
    ],
    "textes": {
        "bloc": {"haut": "we press high", "median": "the block goes back to mid", "bas": "we drop into a low block"},
        "tempo": {"possession": "we keep the ball", "equilibre": "the tempo goes back to normal", "direct": "we play direct"},
        "risque": {"offensif": "we attack", "equilibre": "we play normally again", "prudent": "we close the game down"},
        "lateraux": {"couloir": "the full-backs overlap down their flank", "bas": "the full-backs stay back", "axe": "the full-backs tuck inside"},
        "ailiers": {"equilibre": "the wingers play normally", "ligne": "the wingers hug the touchline", "interieur": "the wingers cut inside"},
        "milieux": {"equilibre": "the midfielders play normally", "projection": "the midfielders get forward", "bas": "the midfielders stay back", "lateral": "the midfielders play it wide"},
        "attaquants": {"equilibre": "the forwards play normally", "profondeur": "the forwards run in behind", "pivot": "the forwards hold it up, back to goal"},
        "relance": {"equilibre": "we build up normally", "courte": "we play out from the back", "longue": "we go long"},
        "formation": "we switch to a {formation}",
        "marquage": "{qui} will be marked tightly",
        "demarquage": "we drop the marking",
        "changement": "{entrant} comes on for {sortant} at the next stoppage",
        "permutation": "{un} and {deux} swap positions",
        "causerie": {"secouer": "you shake them up", "rassurer": "you reassure them", "feliciter": "you praise them", "rien": "you say nothing"},
        "joueur": "{nom} and his line: {texte}",
        "chercher": "The engine cannot yet ask a player to look for another one: tell him where to play instead (\"{nom}, cut inside\", \"{nom}, run in behind\").",
        "tirer": "The shots are theirs to decide: you can ask them to attack (\"attack\") or to play direct.",
        "centrer": "Crosses come from wingers who hug the touchline (\"wingers stay wide\") and from full-backs who overlap.",
        "incompris": "I did not understand. Try for instance: {exemples}.",
        "deja": "That is already what they do.",
        "qui": "I do not know who you mean: {noms}.",
        "banc": "{nom} is not on your bench.",
        "terrain": "{nom} is not on the pitch.",
        "adversaire": "{nom} is not playing for them.",
        "permutation_deux": "For a swap I need two players on the pitch.",
        "changement_deux": "For a substitution I need one player on the pitch and one on the bench.",
        "pas_mi_temps": "You talk to your team at half-time; for now, give them an instruction.",
    },
    "exemples": ["press high", "full-backs stay back", "{adv}, mark him", "{banc} replaces {terrain}", "switch to a 4-4-2", "keep the ball"],
    "guillemets": ("“", "”"),
}

LANGUE_DEFAUT = "fr"


# --------------------------------------------------------------------------
# La normalisation et les noms
# --------------------------------------------------------------------------
def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans ponctuation, un seul espace."""
    s = unicodedata.normalize("NFKD", texte or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


def _formes(nom: str) -> list[str]:
    """Les façons de nommer un joueur : son nom complet, son nom de famille (les
    mots après le prénom, y compris « De Silvestri »), chaque mot de trois lettres
    et plus.  Le plus long d'abord : « Kolo Muani » avant « Muani »."""
    n = normaliser(nom).strip()
    mots = n.split()
    formes = {n}
    if len(mots) > 1:
        formes.add(" ".join(mots[1:]))
    formes |= {m for m in mots if len(m) >= 3}
    return sorted(formes, key=len, reverse=True)


def trouver_noms(phrase: str, joueurs: list[dict]) -> list[tuple[int, dict, int]]:
    """Les joueurs nommés dans la phrase (normalisée), dans l'ordre où ils y sont :
    (position, joueur, longueur du nom reconnu).  Un nom pris n'est pas repris par
    un autre joueur (« Mendes » quand il y a deux Mendes : le premier, nommé en
    entier, gagne ; sinon les deux sont rendus et l'appelant tranche)."""
    trouves: list[tuple[int, dict, int]] = []
    pris: list[tuple[int, int]] = []
    cands = []
    for j in joueurs:
        for f in _formes(j["nom"]):
            for m in re.finditer(r"(?<= )" + re.escape(f) + r"(?= )", phrase):
                cands.append((-(m.end() - m.start()), m.start(), m.end(), j))
    cands.sort()
    for _, a, b, j in cands:
        if any(not (b <= pa or a >= pb) for pa, pb in pris):
            continue
        if any(t[1]["pid"] == j["pid"] for t in trouves):
            continue
        pris.append((a, b))
        trouves.append((a, j, b - a))
    trouves.sort()
    return trouves


def _sans_noms(phrase: str, trouves: list[tuple[int, dict, int]]) -> str:
    """La phrase sans les noms reconnus (pour que « Mendes » ne déclenche pas « monte »...)."""
    out = phrase
    spans = sorted({(pos, n) for pos, _j, n in trouves}, reverse=True)    # un même nom à nous et à eux : une seule fois
    for pos, n in spans:
        out = out[:pos] + " " + out[pos + n:]
    return re.sub(r"\s+", " ", out)


# --------------------------------------------------------------------------
# Comprendre une phrase
# --------------------------------------------------------------------------
def comprendre(texte: str, contexte: dict, langue: str = LANGUE_DEFAUT) -> dict:
    """Traduit une phrase en levier.

    `contexte` : {"terrain": [joueurs à nous sur le terrain], "banc": [joueurs à
    nous sur le banc], "adversaires": [joueurs d'en face sur le terrain],
    "tactique": la tactique en cours (dict), "formations": [noms connus],
    "mi_temps": bool (la causerie est ouverte)}.  Un joueur : {"pid", "nom", "poste", "fam"}.

    Rend {"action": ..., "confirmation": str, ...} :
      action "tactique"    + "tactique" (la tactique complète à envoyer)
      action "changement"  + "sortant", "entrant"
      action "permutation" + "un", "deux"
      action "causerie"    + "causerie"
      action None          + "confirmation" = la réponse (pas compris, impossible, déjà fait)
    """
    V = VOCABULAIRE.get(langue) or VOCABULAIRE[LANGUE_DEFAUT]
    T = V["textes"]
    phrase = normaliser(texte)
    if not phrase.strip():
        return _incompris(V, contexte)
    terrain = list(contexte.get("terrain") or [])
    banc = list(contexte.get("banc") or [])
    adversaires = list(contexte.get("adversaires") or [])
    tac = dict(contexte.get("tactique") or {})

    # 1. les noms : les nôtres, puis ceux d'en face
    notres = trouver_noms(phrase, terrain + banc)
    eux = trouver_noms(phrase, adversaires)
    reste = _sans_noms(phrase, notres + eux)
    sur_terrain = {j["pid"] for j in terrain}
    sur_banc = {j["pid"] for j in banc}

    # 2. le marquage : un joueur d'en face nommé, et un verbe de marquage (ou aucun verbe)
    if re.search(V["demarquage"], reste):
        if not tac.get("marquage"):
            return {"action": None, "confirmation": T["deja"]}
        return {"action": "tactique", "tactique": tac | {"marquage": 0}, "confirmation": _maj(T["demarquage"])}
    if eux and (re.search(V["marquage"], reste) or not notres):
        pid, j = eux[0][1]["pid"], eux[0][1]
        if tac.get("marquage") == pid:
            return {"action": None, "confirmation": T["deja"]}
        return {"action": "tactique", "tactique": tac | {"marquage": pid},
                "confirmation": _maj(T["marquage"].format(qui=j["nom"]))}

    # 3. deux des nôtres : une permutation (deux sur le terrain) ou un changement (un et un)
    if len(notres) >= 2:
        a, b = notres[0][1], notres[1][1]
        if re.search(V["permutation"], reste):
            if a["pid"] in sur_terrain and b["pid"] in sur_terrain:
                return {"action": "permutation", "un": a["pid"], "deux": b["pid"],
                        "confirmation": _maj(T["permutation"].format(un=a["nom"], deux=b["nom"]))}
            return {"action": None, "confirmation": T["permutation_deux"]}
        dedans = [j for j in (a, b) if j["pid"] in sur_terrain]
        dehors = [j for j in (a, b) if j["pid"] in sur_banc]
        if len(dedans) == 1 and len(dehors) == 1:
            s, e = dedans[0], dehors[0]
            return {"action": "changement", "sortant": s["pid"], "entrant": e["pid"],
                    "confirmation": _maj(T["changement"].format(entrant=e["nom"], sortant=s["nom"]))}
        if len(dedans) == 2:
            for motif, cle in V["impossible"]:
                if re.search(motif, reste):
                    return {"action": None, "confirmation": T[cle].format(nom=a["nom"])}
            if re.search(V["changement"], reste):
                return {"action": None, "confirmation": T["changement_deux"]}
        if len(dehors) == 2:
            return {"action": None, "confirmation": T["banc"].format(nom=dehors[0]["nom"])}

    # 4. un seul des nôtres : « X sort » (pas d'entrant : on ne devine pas), « X, reste derrière »
    if len(notres) == 1:
        j = notres[0][1]
        if j["pid"] in sur_banc:
            # « fais entrer X » sans sortant : on ne choisit pas à sa place
            return {"action": None, "confirmation": T["changement_deux"]}
        for motif, cle in V["impossible"]:
            if re.search(motif, reste):
                return {"action": None, "confirmation": T[cle].format(nom=j["nom"])}
        ligne = V["joueur"].get(j.get("poste") or "", _ligne_de_fam(j.get("fam")))
        if ligne:
            val = _ordre(V, ligne, reste)
            if val is not None:
                if tac.get(ligne) == val:
                    return {"action": None, "confirmation": T["deja"]}
                return {"action": "tactique", "tactique": tac | {ligne: val},
                        "confirmation": _maj(T["joueur"].format(nom=j["nom"], texte=T[ligne][val]))}
        if re.search(V["changement"], reste):
            return {"action": None, "confirmation": T["changement_deux"]}

    # 5. l'équipe : la formation, les trois axes, les lignes — plusieurs à la fois
    neuf: dict = {}
    textes: list[str] = []
    deja = False
    m = re.search(r"\b(\d(?: \d){2,4})\b", reste)
    if m:
        forme = m.group(1).replace(" ", "-")
        connues = list(contexte.get("formations") or [])
        if forme in connues:
            if tac.get("formation") != forme:
                neuf["formation"] = forme
                textes.append(T["formation"].format(formation=forme))
            else:
                deja = True
        elif connues:
            g = V.get("guillemets", ("« ", " »"))
            return {"action": None, "confirmation": T["incompris"].format(exemples=", ".join(g[0] + T["formation"].format(formation=f) + g[1] for f in connues[:3]))}
    for motif, levier in V["equipe"]:
        if re.search(motif, reste):
            for k, v in levier.items():
                if k in neuf:
                    continue
                if tac.get(k, "median" if k == "bloc" else "equilibre") != v:
                    neuf[k] = v
                    textes.append(T[k][v])
                else:
                    deja = True
    for ligne, (motif_ligne, _ordres) in V["lignes"].items():
        if re.search(motif_ligne, reste):
            val = _ordre(V, ligne, reste)
            if val is None or ligne in neuf:
                continue
            if tac.get(ligne, _defaut(ligne)) == val:
                deja = True
            else:
                neuf[ligne] = val
                textes.append(T[ligne][val])
    if neuf:
        return {"action": "tactique", "tactique": tac | neuf, "confirmation": _maj(", ".join(textes))}
    if deja:
        return {"action": None, "confirmation": T["deja"]}

    # 6. la causerie (à la pause seulement, et quand rien d'autre n'a pris)
    for motif, val in V["causerie"]:
        if re.search(motif, reste):
            if contexte.get("mi_temps"):
                return {"action": "causerie", "causerie": val, "confirmation": _maj(T["causerie"][val])}
            return {"action": None, "confirmation": T["pas_mi_temps"]}

    for motif, cle in V["impossible"]:
        if re.search(motif, reste):
            return {"action": None, "confirmation": T[cle].format(nom=(terrain[0]["nom"] if terrain else "lui"))}
    return _incompris(V, contexte)


def _ordre(V: dict, ligne: str, reste: str) -> str | None:
    for motif, val in V["lignes"][ligne][1]:
        if re.search(motif, reste):
            return val
    return None


def _ligne_de_fam(fam: str | None) -> str | None:
    return {"DEF": "lateraux", "MID": "milieux", "FWD": "attaquants", "GK": "relance"}.get(fam or "")


def _defaut(ligne: str) -> str:
    return "couloir" if ligne == "lateraux" else "equilibre"


def _maj(s: str) -> str:
    return (s[:1].upper() + s[1:] + ".") if s else s


def _incompris(V: dict, contexte: dict) -> dict:
    terrain = list(contexte.get("terrain") or [])
    banc = list(contexte.get("banc") or [])
    adv = list(contexte.get("adversaires") or [])
    noms = {"adv": adv[-1]["nom"] if adv else "Mbappé", "banc": banc[0]["nom"] if banc else "Kolo Muani",
            "terrain": terrain[-1]["nom"] if terrain else "Dembélé"}
    exemples = [e.format(**noms) for e in V["exemples"]]
    g = V.get("guillemets", ("« ", " »"))
    return {"action": None, "confirmation": V["textes"]["incompris"].format(exemples=", ".join(g[0] + e + g[1] for e in exemples[:4]))}


def exemples(contexte: dict, langue: str = LANGUE_DEFAUT) -> list[str]:
    """Les phrases qu'on propose à l'écran, dans la situation du moment."""
    V = VOCABULAIRE.get(langue) or VOCABULAIRE[LANGUE_DEFAUT]
    terrain = list(contexte.get("terrain") or [])
    banc = list(contexte.get("banc") or [])
    adv = list(contexte.get("adversaires") or [])
    noms = {"adv": adv[-1]["nom"] if adv else "Mbappé", "banc": banc[0]["nom"] if banc else "Kolo Muani",
            "terrain": terrain[-1]["nom"] if terrain else "Dembélé"}
    return [e.format(**noms) for e in V["exemples"]]
