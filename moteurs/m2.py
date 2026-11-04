#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M2 : DECISION SPORTIVE AUTONOME

MISSION
-------
Analyser independamment les forces et faiblesses
des chevaux et produire cinq positions predites
uniquement lorsque les donnees sont suffisantes.

CRITERES M2
-----------
- Forme recente : 25 %
- Opposition : 20 %
- Regularite : 20 %
- Aptitude aux conditions : 20 %
- Potentiel de progression : 15 %

Ces ponderations sont une proposition M2.
Elles doivent etre validees avec le projet existant.

SECURITE
--------
- Courses PMU francaises controlees par le noyau.
- Depart futur controle par le noyau.
- Partants et non-partants controles par le noyau.
- Aucune donnee sportive inventee.
- Aucun classement complet sans donnees suffisantes.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucun FIGE automatique ou retroactif.
- Aucune ecriture dans les archives.
- Aucune modification du depot.

COMMANDES
---------
python -m py_compile moteurs/m2.py
python -m moteurs.m2 --self-test
python -m moteurs.m2 --input courses.json

La commande --input depend du noyau commun.
"""

from __future__ import annotations

import copy
import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITE M2
# ============================================================

MOTEUR = "M2"
VERSION = "2.4"
CHAMP = "decision_sportive"

COUVERTURE_MIN = 1.0

_POIDS_REFERENCE = (
    ("forme_recente", 0.25),
    ("opposition", 0.20),
    ("regularite", 0.20),
    ("aptitude_conditions", 0.20),
    ("potentiel_progression", 0.15),
)

POIDS = dict(_POIDS_REFERENCE)

CRITERES = tuple(
    critere for critere, _ in _POIDS_REFERENCE
)

STATUTS_AUTORISES = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


# ============================================================
# 3. CONFIGURATION M2
# ============================================================

def verifier_configuration() -> None:

    if MOTEUR != "M2":
        raise RuntimeError(
            "Identite M2 incorrecte"
        )

    if VERSION != "2.4":
        raise RuntimeError(
            "Version M2 incorrecte"
        )

    if CHAMP != "decision_sportive":
        raise RuntimeError(
            "Champ M2 incorrect"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or COUVERTURE_MIN != 1.0
    ):
        raise RuntimeError(
            "Couverture minimale incorrecte"
        )

    if POIDS != dict(_POIDS_REFERENCE):
        raise RuntimeError(
            "Ponderations M2 modifiees"
        )

    if len(CRITERES) != 5:
        raise RuntimeError(
            "M2 exige cinq criteres"
        )

    if len(set(CRITERES)) != 5:
        raise RuntimeError(
            "Criteres M2 en double"
        )

    if tuple(POIDS) != CRITERES:
        raise RuntimeError(
            "Ordre des criteres incorrect"
        )

    for critere, poids in POIDS.items():

        if (
            type(poids) not in (int, float)
            or not math.isfinite(poids)
            or poids <= 0
        ):
            raise RuntimeError(
                f"Poids invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "Somme des ponderations incorrecte"
        )


# ============================================================
# 4. COMPATIBILITE DU NOYAU
# ============================================================

def verifier_noyau() -> None:

    verifier_configuration()

    version = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if str(version) != VERSION:
        raise RuntimeError(
            f"Noyau incompatible : {version}"
        )

    for fonction in (
        "analyser_course",
        "executer",
        "note_valide",
    ):

        if not callable(
            getattr(noyau_commun, fonction, None)
        ):
            raise RuntimeError(
                f"Fonction absente : {fonction}"
            )

    statuts = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if not isinstance(
        statuts,
        (set, frozenset, list, tuple),
    ):
        raise RuntimeError(
            "Statuts du noyau invalides"
        )

    try:
        statuts_reels = set(statuts)
    except TypeError as erreur:
        raise RuntimeError(
            "Statuts non exploitables"
        ) from erreur

    if statuts_reels != STATUTS_AUTORISES:
        raise RuntimeError(
            "Statuts incompatibles"
        )


# ============================================================
# 5. CONTROLES NUMERIQUES
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
# 6. VERIFICATION DES CHEVAUX
# ============================================================

def verifier_analyses(resultat: dict) -> dict:

    analyses = resultat.get("chevaux_analyses")

    if not isinstance(analyses, list):
        raise RuntimeError(
            "Liste des chevaux invalide"
        )

    correspondance = {}

    for cheval in analyses:

        if not isinstance(cheval, dict):
            raise RuntimeError(
                "Analyse de cheval invalide"
            )

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
                "Numero invalide ou en double"
            )

        if (
            not isinstance(nom, str)
            or not nom.strip()
        ):
            raise RuntimeError(
                "Nom du cheval invalide"
            )

        if not couverture_valide(couverture):
            raise RuntimeError(
                "Couverture invalide"
            )

        if score is not None:

            if not score_valide(score):
                raise RuntimeError(
                    "Score invalide"
                )

            if not math.isclose(
                couverture,
                1.0,
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                raise RuntimeError(
                    "Score sans couverture complete"
                )

        if type(admissible) is not bool:
            raise RuntimeError(
                "Admissibilite invalide"
            )

        if admissible != (score is not None):
            raise RuntimeError(
                "Admissibilite incoherente"
            )

        correspondance[numero] = cheval

    return correspondance


# ============================================================
# 7. CLASSEMENTS M2
# ============================================================

def verifier_classement(
    resultat: dict,
    analyses: dict,
) -> None:

    statut = resultat["statut"]

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(classement, list):
        raise RuntimeError(
            "Classement invalide"
        )

    if not isinstance(partiel, list):
        raise RuntimeError(
            "Classement partiel invalide"
        )

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel incoherent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit"
        )

    for champ in (
        "classement",
        "classement_partiel",
    ):

        numeros = set()

        for rang, cheval in enumerate(
            resultat[champ],
            start=1,
        ):

            if not isinstance(cheval, dict):
                raise RuntimeError(
                    "Entree de classement invalide"
                )

            numero = cheval.get("numero")
            position = cheval.get(
                "position_predite"
            )

            if (
                type(numero) is not int
                or numero not in analyses
                or numero in numeros
            ):
                raise RuntimeError(
                    "Cheval classe invalide"
                )

            numeros.add(numero)

            if (
                type(position) is not int
                or position != rang
            ):
                raise RuntimeError(
                    "Position predite invalide"
                )

            analyse = analyses[numero]
            score = cheval.get("score")

            if not score_valide(score):
                raise RuntimeError(
                    "Score de classement invalide"
                )

            if score != analyse["score"]:
                raise RuntimeError(
                    "Score incoherent"
                )

            if cheval.get("nom") != analyse["nom"]:
                raise RuntimeError(
                    "Nom du cheval incoherent"
                )

            if (
                "score_m2" in cheval
                and cheval["score_m2"] != score
            ):
                raise RuntimeError(
                    "Score M2 incoherent"
                )


# ============================================================
# 8. VALIDATION COMPLETE
# ============================================================

def verifier_resultat(resultat: Any) -> dict:

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat M2 invalide"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identite M2 incorrecte"
        )

    if str(resultat.get("version")) != VERSION:
        raise RuntimeError(
            "Version du resultat incorrecte"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGE interdit"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_AUTORISES:
        raise RuntimeError(
            "Statut M2 invalide"
        )

    analyses = verifier_analyses(resultat)

    verifier_classement(
        resultat,
        analyses,
    )

    return resultat


# ============================================================
# 9. ANALYSE AUTONOME M2
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Decision sportive propre a M2.

    Les criteres et ponderations sont ceux de M2.
    Le noyau valide les conditions et les scores.

    Aucune prediction n'est fabriquee
    lorsque les donnees sont insuffisantes.
    """

    verifier_noyau()

    try:
        copie = copy.deepcopy(course)
        reference = copy.deepcopy(copie)
    except Exception as erreur:
        raise RuntimeError(
            "Copie de la course impossible"
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

    if type(comparaison) is not bool:
        raise RuntimeError(
            "Comparaison ambigue"
        )

    if not comparaison:
        raise RuntimeError(
            "Le noyau a modifie la course"
        )

    return verifier_resultat(resultat)


# ============================================================
# 10. INTERFACE COORDINATEUR
# ============================================================

def analyser_course_m2(course: Any) -> dict:

    return analyser_course(course)


# ============================================================
# 11. CLASSE MOTEUR M2
# ============================================================

class MoteurM2:

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
# 12. AUTOTEST M2
# ============================================================

def self_test() -> bool:

    verifier_noyau()

    moteur = MoteurM2()
    configuration = moteur.configuration()

    if configuration["moteur"] != "M2":
        raise RuntimeError(
            "Identite M2 invalide"
        )

    if len(configuration["criteres"]) != 5:
        raise RuntimeError(
            "Criteres incomplets"
        )

    if not math.isclose(
        math.fsum(
            configuration["poids"].values()
        ),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "Ponderations invalides"
        )

    if not callable(moteur.analyser):
        raise RuntimeError(
            "Analyse indisponible"
        )

    if not callable(analyser_course_m2):
        raise RuntimeError(
            "Interface indisponible"
        )

    if configuration["publication"] is not False:
        raise RuntimeError(
            "Publication active"
        )

    if configuration["fige_automatique"] is not False:
        raise RuntimeError(
            "FIGE automatique actif"
        )

    if score_valide(True):
        raise RuntimeError(
            "Booleen accepte comme score"
        )

    if score_valide(float("nan")):
        raise RuntimeError(
            "NaN accepte"
        )

    if couverture_valide(float("inf")):
        raise RuntimeError(
            "Infini accepte"
        )

    resultat_invalide = {
        "moteur": "M2",
        "version": VERSION,
        "fige": False,
        "publication": False,
        "statut": "ANALYSE_DISPONIBLE",
        "chevaux_analyses": [],
        "classement": [],
        "classement_partiel": [],
    }

    try:
        verifier_resultat(resultat_invalide)
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "Classement invalide accepte"
        )

    return True


# ============================================================
# 13. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Codes :
    0 : succes
    1 : erreur technique
    2 : donnees insuffisantes / non analysable
    """

    try:
        arguments = sys.argv[1:]

        if "--self-test" in arguments:

            if arguments != ["--self-test"]:
                raise RuntimeError(
                    "--self-test doit etre utilise seul"
                )

            self_test()

            print("X1000 V2.4 - M2")
            print("SELF-TEST : OK")
            print("Configuration : conforme")
            print("Criteres : 5")
            print("Decision : autonome")
            print("Couverture minimale : 100 %")
            print("Collecte PMU : aucune")
            print("Publication : desactivee")
            print("FIGE automatique : desactive")
            print("Archives : aucune modification")

            return 0

        verifier_noyau()

        code = noyau_commun.executer(
            analyser_course
        )

        if (
            type(code) is not int
            or code not in (0, 1, 2)
        ):
            raise RuntimeError(
                "Code de sortie invalide"
            )

        return code

    except Exception as erreur:

        print(
            "ERREUR TECHNIQUE M2 : "
            f"{type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 14. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
