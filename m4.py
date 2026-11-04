#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M4 : TERRAIN, DISTANCE ET PARCOURS

Moteur sportif independant.

CRITERES
--------
Terrain : 25 %
Distance : 25 %
Parcours : 20 %
Conditions : 15 %
Adaptabilite : 15 %

SECURITE
--------
Aucune collecte PMU.
Aucune donnee inventee.
Aucune publication.
Aucun FIGE automatique ou retroactif.
Aucune modification des archives ou du depot.
Controles de course delegues au noyau commun.
"""

from __future__ import annotations

import copy
import math
import sys
from typing import Any

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


MOTEUR = "M4"
VERSION = "2.4"
CHAMP = "aptitude_parcours"
COUVERTURE_MIN = 1.0

_POIDS_REFERENCE = (
    ("terrain", 0.25),
    ("distance", 0.25),
    ("parcours", 0.20),
    ("conditions", 0.15),
    ("adaptabilite", 0.15),
)

POIDS = dict(_POIDS_REFERENCE)
CRITERES = tuple(POIDS)

STATUTS_AUTORISES = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    if MOTEUR != "M4" or VERSION != "2.4":
        raise RuntimeError("Configuration M4 invalide")

    if CHAMP != "aptitude_parcours":
        raise RuntimeError("Champ M4 invalide")

    if COUVERTURE_MIN != 1.0:
        raise RuntimeError("Couverture M4 invalide")

    if POIDS != dict(_POIDS_REFERENCE):
        raise RuntimeError("Ponderations M4 modifiees")

    if len(POIDS) != 5:
        raise RuntimeError("Cinq criteres obligatoires")

    if any(
        type(v) not in (int, float)
        or not math.isfinite(v)
        or v <= 0
        for v in POIDS.values()
    ):
        raise RuntimeError("Poids M4 invalides")

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise RuntimeError("Somme des poids incorrecte")


# ============================================================
# NOYAU COMMUN
# ============================================================

def verifier_noyau() -> None:
    verifier_configuration()

    version = getattr(noyau_commun, "VERSION", None)

    if str(version) != VERSION:
        raise RuntimeError(
            f"Noyau incompatible : {version}"
        )

    for nom in (
        "analyser_course",
        "executer",
        "note_valide",
    ):
        if not callable(getattr(noyau_commun, nom, None)):
            raise RuntimeError(
                f"Fonction absente : {nom}"
            )

    statuts = getattr(
        noyau_commun, "STATUTS_VALIDES", None
    )

    if not isinstance(
        statuts, (set, frozenset, tuple, list)
    ):
        raise RuntimeError("Statuts du noyau invalides")

    try:
        ensemble = set(statuts)
    except TypeError as erreur:
        raise RuntimeError(
            "Statuts du noyau non exploitables"
        ) from erreur

    if ensemble != STATUTS_AUTORISES:
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


# ============================================================
# CONTROLES NUMERIQUES
# ============================================================

def score_valide(valeur: Any) -> bool:
    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 100
    )


def couverture_valide(valeur: Any) -> bool:
    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 1
    )


# ============================================================
# VALIDATION DES ANALYSES
# ============================================================

def verifier_analyses(resultat: dict) -> dict:
    analyses = resultat.get("chevaux_analyses")

    if not isinstance(analyses, list):
        raise RuntimeError("Analyses M4 invalides")

    correspondance = {}

    for cheval in analyses:
        if not isinstance(cheval, dict):
            raise RuntimeError("Cheval invalide")

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        score = cheval.get("score")
        couverture = cheval.get("couverture")
        admissible = cheval.get("admissible")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in correspondance
        ):
            raise RuntimeError(
                "Numero invalide ou duplique"
            )

        if not isinstance(nom, str) or not nom.strip():
            raise RuntimeError("Nom invalide")

        if not couverture_valide(couverture):
            raise RuntimeError("Couverture invalide")

        if score is not None:
            if not score_valide(score):
                raise RuntimeError("Score invalide")

            if not math.isclose(
                couverture, 1.0,
                rel_tol=0,
                abs_tol=1e-6,
            ):
                raise RuntimeError(
                    "Score sans couverture complete"
                )

        if type(admissible) is not bool:
            raise RuntimeError(
                "Admissibilite non booleenne"
            )

        if admissible != (score is not None):
            raise RuntimeError(
                "Admissibilite incoherente"
            )

        correspondance[numero] = cheval

    return correspondance


# ============================================================
# VALIDATION DES CLASSEMENTS
# ============================================================

def verifier_classement(
    resultat: dict,
    analyses: dict,
) -> None:
    statut = resultat["statut"]
    complet = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(complet, list):
        raise RuntimeError("Classement M4 invalide")

    if not isinstance(partiel, list):
        raise RuntimeError(
            "Classement partiel invalide"
        )

    if statut == "ANALYSE_DISPONIBLE":
        if len(complet) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":
        if complet or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel incoherent"
            )

    elif complet or partiel:
        raise RuntimeError("Classement interdit")

    for liste in (complet, partiel):
        numeros = set()
        score_precedent = None

        for rang, cheval in enumerate(liste, start=1):
            if not isinstance(cheval, dict):
                raise RuntimeError(
                    "Entree de classement invalide"
                )

            numero = cheval.get("numero")
            position = cheval.get("position_predite")
            score = cheval.get("score")

            if (
                type(numero) is not int
                or numero not in analyses
                or numero in numeros
            ):
                raise RuntimeError(
                    "Cheval classe invalide"
                )

            numeros.add(numero)

            if type(position) is not int or position != rang:
                raise RuntimeError(
                    "Position predite invalide"
                )

            if not score_valide(score):
                raise RuntimeError(
                    "Score de classement invalide"
                )

            analyse = analyses[numero]

            if score != analyse["score"]:
                raise RuntimeError(
                    "Score de classement incoherent"
                )

            if cheval.get("nom") != analyse["nom"]:
                raise RuntimeError(
                    "Nom de classement incoherent"
                )

            if (
                "score_m4" in cheval
                and cheval["score_m4"] != score
            ):
                raise RuntimeError(
                    "Score M4 incoherent"
                )

            if (
                score_precedent is not None
                and score > score_precedent
            ):
                raise RuntimeError(
                    "Classement non decroissant en score"
                )

            score_precedent = score


# ============================================================
# VALIDATION DU RESULTAT
# ============================================================

def verifier_resultat(resultat: Any) -> dict:
    if not isinstance(resultat, dict):
        raise RuntimeError("Resultat M4 invalide")

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError("Identite M4 incorrecte")

    if str(resultat.get("version")) != VERSION:
        raise RuntimeError("Version M4 incorrecte")

    if resultat.get("fige") is not False:
        raise RuntimeError("FIGE interdit")

    if resultat.get("publication") is not False:
        raise RuntimeError("Publication interdite")

    statut = resultat.get("statut")

    if statut not in STATUTS_AUTORISES:
        raise RuntimeError("Statut M4 invalide")

    analyses = verifier_analyses(resultat)
    verifier_classement(resultat, analyses)

    return resultat


# ============================================================
# ANALYSE SPORTIVE M4
# ============================================================

def analyser_course(course: Any) -> dict:
    verifier_noyau()

    try:
        copie = copy.deepcopy(course)
        reference = copy.deepcopy(copie)
    except Exception as erreur:
        raise RuntimeError(
            "Copie de course impossible"
        ) from erreur

    resultat = noyau_commun.analyser_course(
        course=copie,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    try:
        comparaison = copie == reference
    except Exception as erreur:
        raise RuntimeError(
            "Comparaison impossible"
        ) from erreur

    if type(comparaison) is not bool or not comparaison:
        raise RuntimeError(
            "Le noyau a modifie les donnees d'entree"
        )

    return verifier_resultat(resultat)


def analyser_course_m4(course: Any) -> dict:
    return analyser_course(course)


# ============================================================
# CLASSE M4
# ============================================================

class MoteurM4:
    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def __init__(self) -> None:
        verifier_noyau()

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def configuration(self) -> dict:
        return {
            "moteur": MOTEUR,
            "version": VERSION,
            "champ": CHAMP,
            "criteres": list(CRITERES),
            "poids": POIDS.copy(),
            "couverture_min": COUVERTURE_MIN,
            "publication": False,
            "fige_automatique": False,
        }


# ============================================================
# AUTOTEST
# ============================================================

def self_test() -> bool:
    verifier_noyau()

    moteur = MoteurM4()
    configuration = moteur.configuration()

    if configuration["moteur"] != "M4":
        raise RuntimeError("Identite M4 invalide")

    if len(configuration["criteres"]) != 5:
        raise RuntimeError("Criteres incomplets")

    if not callable(moteur.analyser):
        raise RuntimeError("Analyse indisponible")

    if not callable(analyser_course_m4):
        raise RuntimeError("Interface indisponible")

    if score_valide(True) or score_valide(float("nan")):
        raise RuntimeError(
            "Validation numerique incorrecte"
        )

    if couverture_valide(float("inf")):
        raise RuntimeError(
            "Couverture infinie acceptee"
        )

    invalide = {
        "moteur": "M4",
        "version": VERSION,
        "fige": False,
        "publication": False,
        "statut": "ANALYSE_DISPONIBLE",
        "chevaux_analyses": [],
        "classement": [],
        "classement_partiel": [],
    }

    try:
        verifier_resultat(invalide)
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "Classement invalide accepte"
        )

    return True


# ============================================================
# EXECUTION
# ============================================================

def main() -> int:
    try:
        arguments = sys.argv[1:]

        if "--self-test" in arguments:
            if arguments != ["--self-test"]:
                raise RuntimeError(
                    "--self-test doit etre utilise seul"
                )

            self_test()
            print("X1000 V2.4 - M4")
            print("SELF-TEST : OK")
            print("Criteres : 5")
            print("Couverture minimale : 100 %")
            print("Publication : desactivee")
            print("FIGE automatique : desactive")
            print("Archives : inchangees")
            return 0

        verifier_noyau()
        code = noyau_commun.executer(analyser_course)

        if type(code) is not int or code not in (0, 1, 2):
            raise RuntimeError(
                "Code de sortie du noyau invalide"
            )

        return code

    except Exception as erreur:
        print(
            f"ERREUR M4 : {type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
