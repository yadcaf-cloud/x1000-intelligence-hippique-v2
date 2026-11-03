#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.3 — M3 : Outsiders et favoris vulnérables.

MISSION :
- Analyse indépendante du moteur M3.
- Détection heuristique des outsiders potentiels.
- Recherche des favoris sportivement vulnérables.
- Exclusion des non-partants.
- Aucune cote ou note inventée.
- Conservation des classements partiels.
- Aucune écriture, publication ou création de FIGÉ.

Les cotes doivent provenir d'une source documentée.
Les signaux M3 ne garantissent aucun résultat.
"""

import math
import sys

if __package__:
    from .noyau_commun import analyser_course, executer
else:
    from noyau_commun import analyser_course, executer


MOTEUR = "M3"
VERSION = "2.3"

CHAMP = "indicateurs_m3"
COUVERTURE_MIN = 0.65

POIDS = {
    "forme": 0.25,
    "progression": 0.25,
    "aptitude_parcours": 0.20,
    "regularite": 0.15,
    "potentiel_surprise": 0.15,
}

# Seuils heuristiques propres au moteur M3.
COTE_MIN_OUTSIDER = 10.0
SCORE_MIN_OUTSIDER = 70.0

COTE_MAX_FAVORI = 4.0
SCORE_MAX_FAVORI_FAIBLE = 55.0


def cote_valide(valeur):
    """Valide une cote décimale sans en inventer."""

    if valeur is None or isinstance(valeur, bool):
        return None

    if isinstance(valeur, str):
        valeur = valeur.strip().replace(",", ".")
        if not valeur:
            return None

    try:
        cote = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(cote):
        return None

    if cote <= 1:
        return None

    return cote


def analyser_course_m3(course):
    """Analyse sportive et signaux de marché du moteur M3."""

    resultat = analyser_course(
        course=course,
        moteur=MOTEUR,
        poids=POIDS,
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    resultat["version_moteur"] = VERSION

    resultat["parametres_m3"] = {
        "cote_min_outsider": COTE_MIN_OUTSIDER,
        "score_min_outsider": SCORE_MIN_OUTSIDER,
        "cote_max_favori": COTE_MAX_FAVORI,
        "score_max_favori_faible": SCORE_MAX_FAVORI_FAIBLE,
    }

    resultat["avertissement_m3"] = (
        "Signaux heuristiques fondes sur les indicateurs "
        "fournis et les cotes disponibles. "
        "Aucune prediction garantie."
    )

    # Une course non analysable ne doit produire
    # aucun signal de marché.
    if resultat["statut"] == "NON_ANALYSABLE":
        return resultat

    # Les classements partiels restent exploitables
    # pour l'examen des chevaux admissibles.
    if resultat["statut"] not in (
        "ANALYSE_DISPONIBLE",
        "DONNEES_INSUFFISANTES",
    ):
        return resultat

    chevaux = {
        cheval["numero"]: cheval
        for cheval in course["partants"]
        if not cheval["non_partant"]
    }

    outsiders = []
    favoris_fragiles = []

    for analyse in resultat["chevaux_analyses"]:

        if not analyse["admissible"]:
            continue

        numero = analyse["numero"]
        cheval = chevaux.get(numero)

        if cheval is None:
            continue

        cote = cote_valide(cheval.get("cote"))
        score = analyse["score"]

        if cote is None or score is None:
            continue

        informations = {
            "numero": numero,
            "nom": analyse["nom"],
            "cote": cote,
            "score_m3": score,
            "couverture": analyse["couverture"],
        }

        if (
            cote >= COTE_MIN_OUTSIDER
            and score >= SCORE_MIN_OUTSIDER
        ):
            outsiders.append({
                **informations,
                "motif": (
                    "Cote elevee et indicateurs M3 "
                    "favorables. Outsider potentiel, "
                    "sans garantie de performance."
                ),
            })

        if (
            cote <= COTE_MAX_FAVORI
            and score < SCORE_MAX_FAVORI_FAIBLE
        ):
            favoris_fragiles.append({
                **informations,
                "motif": (
                    "Cote basse et indicateurs M3 "
                    "relativement faibles. "
                    "Favori a examiner."
                ),
            })

    outsiders.sort(
        key=lambda cheval: (
            -cheval["score_m3"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    favoris_fragiles.sort(
        key=lambda cheval: (
            cheval["score_m3"],
            cheval["cote"],
            cheval["numero"],
        )
    )

    resultat["outsiders_potentiels"] = outsiders
    resultat["favoris_a_examiner"] = favoris_fragiles

    resultat["signaux_m3"] = {
        "nombre_outsiders": len(outsiders),
        "nombre_favoris_a_examiner": len(favoris_fragiles),
        "cotes_manquantes_ou_invalides": sum(
            1
            for analyse in resultat["chevaux_analyses"]
            if analyse["admissible"]
            and cote_valide(
                chevaux[analyse["numero"]].get("cote")
            ) is None
        ),
    }

    return resultat


class MoteurM3:
    nom = MOTEUR
    version = VERSION

    def analyser(self, course):
        return analyser_course_m3(course)


if __name__ == "__main__":
    sys.exit(executer(analyser_course_m3))
