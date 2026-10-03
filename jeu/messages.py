"""Les messages du jeu, par code (PLAN.md § 3, les langues).

Une règle qui refuse quelque chose ne renvoie plus une phrase mais un CODE et
ses paramètres (`budget_insuffisant`, prix=25.0) : c'est l'écran qui traduit
(`web/app/static/lang/<langue>.json`, clés `err.<code>`).  Le français reste
ici comme texte de secours — ce que voit un client sans dictionnaire, et ce
que lisent les tests (`str(err)`).

`ErreurJeu(code, **params)` : `code`, `params`, et `str()` donne le français.
Un code inconnu est pris tel quel comme message (le temps d'une migration).
"""
from __future__ import annotations

MESSAGES: dict[str, str] = {
    # -- le onze, le banc ------------------------------------------------------------
    "formation_inconnue": "Formation inconnue",
    "onze_onze": "Il faut onze joueurs, tous différents",
    "onze_hors_effectif": "Un joueur du onze n'est pas dans ton effectif",
    "joueur_inconnu": "Joueur inconnu",
    "banc_double": "Un remplaçant est en double, ou déjà titulaire",
    "banc_max": "{n} remplaçants au plus",
    "banc_hors_effectif": "Un remplaçant n'est pas dans ton effectif",
    "suspendu": "{nom} est suspendu (encore {n} match{s})",
    "blesse": "{nom} est blessé (encore {n} match{s})",
    # -- le match ------------------------------------------------------------------
    "deja_match": "Tu as déjà un match en cours",
    "aucun_match": "Aucun match en cours",
    "match_termine": "Le match est terminé",
    "causerie_inconnue": "Causerie inconnue",
    "causerie_mi_temps": "C'est à la mi-temps qu'on parle à son équipe",
    "causerie_deja": "Tu leur as déjà parlé",
    "pas_sur_terrain": "Ce joueur n'est pas sur le terrain",
    "pas_sur_banc": "Ce joueur n'est pas sur ton banc",
    "changements_max": "{n} changements, c'est le maximum",
    "deux_joueurs": "Il faut deux joueurs différents",
    "deux_sur_terrain": "Les deux joueurs doivent être sur le terrain",
    "pause_classe": "On ne met pas un match classé en pause",
    "rien_a_quitter": "Rien à quitter : le match a déjà commencé",
    "aucun_match_campagne": "Aucun match de campagne en cours",
    # -- le marché -------------------------------------------------------------------
    "pack_inconnu": "Pack inconnu",
    "poste_inconnu": "Poste inconnu",
    "pack_offert_simple": "Un pack offert est un pack simple, sans poste choisi",
    "pack_pas_offert": "Tu n'as pas de pack de ce type offert",
    "budget_pack": "Budget insuffisant : le pack coûte {prix} M€",
    "reserve_pleine_pack": "Réserve pleine ({n} cartes) : vends ou aligne avant d'ouvrir",
    "pack_epuise": "Plus assez de cartes disponibles pour ce pack",
    "pas_ta_carte": "Cette carte n'est pas à toi",
    "carte_en_vente": "Cette carte est en vente",
    "deja_effectif": "Ce joueur est déjà dans ton effectif",
    "effectif_complet": "Effectif complet ({n})",
    "reserve_pleine": "Réserve pleine ({n})",
    "carte_en_vente_annule": "Cette carte est en vente : annule d'abord",
    "carte_deja_en_vente": "Cette carte est déjà en vente",
    "duree_vente": "Durée : {durees} heures",
    "prix_depart_min": "Prix de départ : 100 k€ au moins",
    "achat_immediat_prix": "Le prix d'achat immédiat doit dépasser le prix de départ",
    "vente_inconnue": "Vente inconnue",
    "vente_terminee": "Cette vente est terminée",
    "ta_vente": "C'est ta propre vente",
    "offre_min": "Offre minimale : {montant} M€",
    "budget_offre": "Budget insuffisant pour cette offre",
    "pas_achat_immediat": "Pas d'achat immédiat sur cette vente",
    "budget": "Budget insuffisant",
    "pas_ta_vente": "Ce n'est pas ta vente",
    "offre_faite": "Une offre a été faite : la vente ira à son terme",
    # -- le solo ---------------------------------------------------------------------
    "competition_inconnue": "Compétition inconnue",
    "deja_campagne": "Tu as déjà une campagne en cours",
    "club_hors_competition": "Ce club ne joue pas cette compétition",
    "aucune_campagne": "Aucune campagne en cours",
    "match_deja_en_cours": "Ton match est déjà en cours",
    "campagne_terminee": "La campagne est terminée",
    "campagne_inconnue": "Campagne inconnue",
    # -- le serveur ------------------------------------------------------------------
    "connecte_toi": "Connecte-toi d'abord",
    "admin": "Réservé à l'administrateur",
    "pseudo_forme": "Pseudo : 2 à 24 lettres, chiffres, - ou _",
    "mdp_court": "Mot de passe : 6 caractères au moins",
    "pseudo_pris": "Ce pseudo est déjà pris",
    "identifiants": "Pseudo ou mot de passe incorrect",
    "carte_inconnue": "Carte inconnue",
    "carte_indisponible": "Carte indisponible",
    "detail_sans_bareme": "Le détail n'est pas disponible : cette base n'a pas de barème.",
    "journee_verrouillee_effectif": "Journée verrouillée : l'effectif ne bouge plus jusqu'à la clôture",
    "montant_manquant": "Montant manquant",
    "saison_terminee": "Saison terminée",
    "journee_verrouillee": "Journée {n} verrouillée depuis le coup d'envoi",
    "compo_doublons": "Composition : joueurs en double ou pas dans l'effectif",
    "capitaine_titulaire": "Le capitaine doit être titulaire",
    "banc_max_feuille": "{n} remplaçants au plus sur la feuille",
    "onze_titulaires": "Il faut onze titulaires",
    "pas_de_resultat": "Pas de résultat pour cette journée",
    "reglage_inconnu": "Réglage tactique inconnu",
    "couleur": "Couleur attendue en #rrggbb",
    "motif_inconnu": "Motif inconnu",
    "ligue_nom_court": "Nom de ligue trop court",
    "code_inconnu": "Code inconnu",
    "tactique_inconnue": "Tactique inconnue",
    "club_sans_onze": "Un des deux clubs n'a pas onze cartes",
    # -- les comptes en ligne, le paiement (jeu/comptes.py, jeu/paiement.py) ------------------
    "limite_matchs": "{n} matchs de campagne ou de défi par jour en gratuit : reviens demain, ou joue en classé",
    "limite_encheres": "{n} enchères en cours au plus en gratuit",
    "naissance_forme": "Date de naissance attendue en AAAA-MM-JJ",
    "email_forme": "Adresse de courriel invalide",
    "jeton_invalide": "Ce lien ne vaut plus : demande un nouveau mot de passe",
    "produit_inconnu": "Produit inconnu",
    "mineur": "Les achats sont réservés aux majeurs",
    "paiement_indisponible": "Le paiement n'est pas ouvert sur ce serveur",
    "signature": "Signature invalide",
    "email_pris": "Ce courriel est déjà utilisé par un compte",
    "compte_inconnu": "Compte inconnu",
    # -- la coupe entre amis (jeu/coupe.py) ---------------------------------------------------
    "pas_membre": "Tu n'es pas membre de cette ligue",
    "coupe_en_cours": "Une coupe est déjà en cours dans cette ligue",
    "coupe_semaine": "La coupe de cette semaine a déjà été jouée : la prochaine lundi",
    "coupe_deux": "Il faut au moins deux membres pour une coupe",
    "coupe_match_inconnu": "Ce match de coupe n'est pas le tien",
    "coupe_match_joue": "Ce match de coupe est déjà joué",
    "coupe_match_en_cours": "Ce match de coupe se joue en ce moment",
    "coupe_match_attend": "Ton adversaire n'est pas encore connu",
}


def texte(code: str, params: dict | None = None) -> str:
    """Le français d'un code (le texte de secours), paramètres compris ;
    `s` vaut « s » quand `n` dépasse un."""
    gabarit = MESSAGES.get(code)
    if gabarit is None:
        return code
    p = dict(params or {})
    if "n" in p and "s" not in p:
        try:
            p["s"] = "s" if float(p["n"]) > 1 else ""
        except (TypeError, ValueError):
            p["s"] = ""
    try:
        return gabarit.format(**p)
    except (KeyError, IndexError, ValueError):
        return gabarit


class ErreurJeu(Exception):
    """Une règle qui refuse : un code, ses paramètres, et le français en `str()`."""

    def __init__(self, code: str, **params):
        self.code = code
        self.params = {k: v for k, v in params.items()}
        super().__init__(texte(code, self.params))

    def detail(self) -> dict:
        """Ce que l'API renvoie : le code, les paramètres, et le français de secours."""
        return {"code": self.code, "params": self.params, "message": str(self)}
