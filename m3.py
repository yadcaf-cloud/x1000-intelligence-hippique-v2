#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M3 : JOCKEY, DRIVER ET ENTOURAGE

MISSION
-------
Produire une analyse sportive M3 independante
a partir de donnees documentees.

CRITERES
--------
- Jockey ou driver : 30 %
- Entraineur : 25 %
- Association cheval / jockey : 20 %
- Experience du parcours : 15 %
- Regularite de l'entourage : 10 %

Les criteres et ponderations sont proposes pour M3.
Le noyau commun doit accepter ces champs.

SECURITE
--------
- Courses PMU en France controlees par le noyau.
- Depart futur controle par le noyau.
- Partants et non-partants verifies par le noyau.
- Aucune donnee inventee.
- Aucun classement complet sans donnees suffisantes.
- Aucun FIGE automatique ou retroactif.
- Aucune collecte PMU par M3.
- Aucune publication automatique.
- Aucune ecriture dans les archives.
- Aucune modification du depot.

COMMANDES
---------
python -m py_compile moteurs/m3.py
python -m moteurs.m3 --self-test
python -m moteurs.m3 --input courses.json

La commande --input depend du noyau commun.
"""

from __future__ import annotations

import copy
import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION
# ============================================================

MOTEUR = "M3"
VERSION = "2.4"
CHAMP = "entourage"

COUVERTURE_MIN = 1.0

_POIDS_REFERENCE = (
    ("jockey_driver", 0.30),
    ("entraineur", 0.25),
    ("association", 0.20),
    ("experience_parcours", 0.15),
    ("regularite_entourage", 0.10),
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
# 2. IMPORT DU NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


# ============================================================
# 3. VALIDATION CONFIGURATION
# ============================================================

def verifier_configuration() -> None:

    if MOTEUR != "M3":
        raise RuntimeError(
            "Identite M3 incorrecte"
        )

    if VERSION != "2.4":
        raise RuntimeError(
            "Version M3 incorrecte"
        )

    if CHAMP != "entourage":
        raise RuntimeError(
            "Champ M3 incorrect"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or COUVERTURE_MIN != 1.0
    ):
        raise RuntimeError(
            "Couverture minimale invalide"
        )

    if POIDS != dict(_POIDS_REFERENCE):
        raise RuntimeError(
            "Ponderations M3 modifiees"
        )

    if len(CRITERES) != 5:
        raise RuntimeError(
            "Cinq criteres obligatoires"
        )

    if len(set(CRITERES)) != 5:
        raise RuntimeError(
            "Criteres en double"
        )

    if tuple(POIDS) != CRITERES:
        raise RuntimeError(
            "Ordre des criteres modifie"
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
            "Somme des poids differente de 1"
        )


# ============================================================
# 4. VERIFICATION DU NOYAU
# ============================================================

def verifier_noyau() -> None:

    verifier_configuration()

    version_noyau = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if str(version_noyau) != VERSION:
        raise RuntimeError(
            "Noyau incompatible : "
            f"M3={VERSION}, noyau={version_noyau}"
        )

    for nom in (
        "analyser_course",
        "executer",
        "note_valide",
    ):

        if not callable(
            getattr(noyau_commun, nom, None)
        ):
            raise RuntimeError(
                f"Fonction du noyau absente : {nom}"
            )

    statuts = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if not isinstance(
        statuts,
        (set, frozenset, tuple, list),
    ):
        raise RuntimeError(
            "Statuts du noyau absents"
        )

    try:
        statuts_reels = set(statuts)
    except TypeError as erreur:
        raise RuntimeError(
            "Statuts du noyau invalides"
        ) from erreur

    if statuts_reels != STATUTS_AUTORISES:
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


# ============================================================
# 5. VALIDATION NUMERIQUE
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
# 6. VALIDATION DES CHEVAUX
# ============================================================

def verifier_analyses(resultat: dict) -> dict:

    analyses = resultat.get("chevaux_analyses")

    if not isinstance(analyses, list):
        raise RuntimeError(
            "Liste des chevaux invalide"
        )

    correspondance = {}

    for analyse in analyses:

        if not isinstance(analyse, dict):
            raise RuntimeError(
                "Analyse individuelle invalide"
            )

        numero = analyse.get("numero")
        nom = analyse.get("nom")
        score = analyse.get("score")
        couverture = analyse.get("couverture")
        admissible = analyse.get("admissible")

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
                "Couverture M3 invalide"
            )

        if score is not None:

            if not score_valide(score):
                raise RuntimeError(
                    "Score M3 invalide"
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

        correspondance[numero] = analyse

    return correspondance


# ============================================================
# 7. VALIDATION DES CLASSEMENTS
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
            "Classement M3 invalide"
        )

    if not isinstance(partiel, list):
        raise RuntimeError(
            "Classement partiel M3 invalide"
        )

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M3 obligatoires"
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
                    "Score de classement incoherent"
                )

            if cheval.get("nom") != analyse["nom"]:
                raise RuntimeError(
                    "Nom du cheval incoherent"
                )

            if (
                "score_m3" in cheval
                and cheval["score_m3"] != score
            ):
                raise RuntimeError(
                    "Score specifique M3 incoherent"
                )


# ============================================================
# 8. VALIDATION DU RESULTAT
# ============================================================

def verifier_resultat(resultat: Any) -> dict:

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat M3 invalide"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identite du resultat incorrecte"
        )

    if str(resultat.get("version")) != VERSION:
        raise RuntimeError(
            "Version du resultat incorrecte"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGE interdit dans M3"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans M3"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_AUTORISES:
        raise RuntimeError(
            "Statut M3 invalide"
        )

    analyses = verifier_analyses(resultat)

    verifier_classement(
        resultat,
        analyses,
    )

    return resultat


# ============================================================
# 9. ANALYSE SPORTIVE M3
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse independante M3.

    Le noyau commun controle les conditions
    de course et calcule les scores fournis.

    M3 refuse les sorties non conformes.
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
            "Comparaison de l'entree impossible"
        ) from erreur

    if type(comparaison) is not bool:
        raise RuntimeError(
            "Comparaison de l'entree ambigue"
        )

    if not comparaison:
        raise RuntimeError(
            "Le noyau a modifie la course"
        )

    return verifier_resultat(resultat)


# ============================================================
# 10. INTERFACE COORDINATEUR
# ============================================================

def analyser_course_m3(course: Any) -> dict:

    return analyser_course(course)


# ============================================================
# 11. CLASSE MOTEUR
# ============================================================

class MoteurM3:

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
# 12. AUTOTEST M3
# ============================================================

def self_test() -> bool:

    verifier_noyau()

    moteur = MoteurM3()
    configuration = moteur.configuration()

    if configuration["moteur"] != "M3":
        raise RuntimeError(
            "Autotest : identite incorrecte"
        )

    if configuration["version"] != "2.4":
        raise RuntimeError(
            "Autotest : version incorrecte"
        )

    if len(configuration["criteres"]) != 5:
        raise RuntimeError(
            "Autotest : criteres incomplets"
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
            "Autotest : ponderations invalides"
        )

    if not callable(moteur.analyser):
        raise RuntimeError(
            "Autotest : analyse indisponible"
        )

    if not callable(analyser_course_m3):
        raise RuntimeError(
            "Autotest : interface indisponible"
        )

    if configuration["publication"] is not False:
        raise RuntimeError(
            "Autotest : publication active"
        )

    if configuration["fige_automatique"] is not False:
        raise RuntimeError(
            "Autotest : FIGE automatique actif"
        )

    if score_valide(float("nan")):
        raise RuntimeError(
            "Autotest : NaN accepte"
        )

    if score_valide(True):
        raise RuntimeError(
            "Autotest : booleen accepte"
        )

    if couverture_valide(float("inf")):
        raise RuntimeError(
            "Autotest : infini accepte"
        )

    resultat_invalide = {
        "moteur": "M3",
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
            "Autotest : classement invalide accepte"
        )

    return True


# ============================================================
# 13. EXECUTION SECURISEE
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

            print("X1000 V2.4 - M3")
            print("SELF-TEST : OK")
            print("Configuration : conforme")
            print("Criteres : 5")
            print("Moteur : independant")
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
                "Code de sortie du noyau invalide"
            )

        return code

    except Exception as erreur:

        print(
            "ERREUR TECHNIQUE M3 : "
            f"{type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 14. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
