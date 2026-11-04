#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M1 : STATISTIQUES ET PERFORMANCES

Moteur sportif indépendant.

CRITERES
--------
- Forme
- Regularite
- Distance
- Parcours
- Performance

PONDERATIONS
------------
20 % par critere.
Couverture minimale : 100 %.

SECURITE
--------
- Courses francaises controlees par le noyau.
- Depart futur controle par le noyau.
- Partants et non-partants verifies par le noyau.
- Aucune donnee sportive inventee.
- Aucun classement complet sans donnees suffisantes.
- Aucun FIGE automatique ou retroactif.
- Aucune collecte PMU par M1.
- Aucune publication par M1.
- Aucune ecriture d'archives par M1.
- Aucune modification du depot par M1.

COMMANDES
---------
python -m py_compile moteurs/m1.py
python -m moteurs.m1 --self-test
python -m moteurs.m1 --input courses.json

La commande --input depend de l'interface du noyau.
Les declarations de verification des donnees ne
constituent pas des preuves d'authenticite.
"""

from __future__ import annotations

import copy
import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION
# ============================================================

MOTEUR = "M1"
VERSION = "2.4"
CHAMP = "statistiques"

COUVERTURE_MIN = 1.0

_POIDS_REFERENCE = (
    ("forme", 0.20),
    ("regularite", 0.20),
    ("distance", 0.20),
    ("parcours", 0.20),
    ("performance", 0.20),
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
    """Controle la configuration propre a M1."""

    if MOTEUR != "M1":
        raise RuntimeError(
            "Identite M1 incorrecte"
        )

    if VERSION != "2.4":
        raise RuntimeError(
            "Version M1 incorrecte"
        )

    if CHAMP != "statistiques":
        raise RuntimeError(
            "Champ M1 incorrect"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or COUVERTURE_MIN != 1.0
    ):
        raise RuntimeError(
            "Couverture minimale incorrecte"
        )

    if not isinstance(POIDS, dict):
        raise RuntimeError(
            "Ponderations invalides"
        )

    if POIDS != dict(_POIDS_REFERENCE):
        raise RuntimeError(
            "Ponderations M1 modifiees"
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
            poids,
            0.20,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise RuntimeError(
                f"Ponderation incorrecte : {critere}"
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
    """Verifie le contrat technique du noyau."""

    verifier_configuration()

    version_noyau = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if str(version_noyau) != VERSION:
        raise RuntimeError(
            "Noyau incompatible : "
            f"M1={VERSION}, noyau={version_noyau}"
        )

    fonctions = (
        "analyser_course",
        "executer",
        "note_valide",
    )

    for nom in fonctions:

        fonction = getattr(
            noyau_commun,
            nom,
            None,
        )

        if not callable(fonction):
            raise RuntimeError(
                "Fonction du noyau indisponible : "
                f"{nom}"
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
    """Accepte uniquement un score fini entre 0 et 100."""

    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 100
    )


def couverture_valide(valeur: Any) -> bool:
    """Accepte une couverture finie entre 0 et 1."""

    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 1
    )


# ============================================================
# 6. VALIDATION DES CHEVAUX
# ============================================================

def verifier_analyses(resultat: dict) -> dict:
    """Controle les analyses individuelles."""

    analyses = resultat.get("chevaux_analyses")

    if not isinstance(analyses, list):
        raise RuntimeError(
            "Liste des chevaux invalide"
        )

    numeros = set()
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

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros
        ):
            raise RuntimeError(
                "Numero invalide ou en double"
            )

        numeros.add(numero)

        if (
            not isinstance(nom, str)
            or not nom.strip()
        ):
            raise RuntimeError(
                "Nom du cheval invalide"
            )

        if not couverture_valide(couverture):
            raise RuntimeError(
                "Couverture statistique invalide"
            )

        if score is not None:

            if not score_valide(score):
                raise RuntimeError(
                    "Score statistique invalide"
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

        admissible = analyse.get("admissible")

        if type(admissible) is not bool:
            raise RuntimeError(
                "Admissibilite non booleenne"
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
    """Controle classements complets et partiels."""

    statut = resultat["statut"]

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(classement, list):
        raise RuntimeError(
            "Classement M1 invalide"
        )

    if not isinstance(partiel, list):
        raise RuntimeError(
            "Classement partiel M1 invalide"
        )

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M1 obligatoires"
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
                "score_m1" in cheval
                and cheval["score_m1"] != score
            ):
                raise RuntimeError(
                    "Score specifique M1 incoherent"
                )


# ============================================================
# 8. VALIDATION DU RESULTAT
# ============================================================

def verifier_resultat(resultat: Any) -> dict:
    """Refuse les sorties non conformes."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat M1 invalide"
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
            "FIGE interdit dans M1"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans M1"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_AUTORISES:
        raise RuntimeError(
            f"Statut non autorise : {statut}"
        )

    analyses = verifier_analyses(resultat)

    verifier_classement(
        resultat,
        analyses,
    )

    return resultat


# ============================================================
# 9. ANALYSE SPORTIVE M1
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse statistique M1.

    Le noyau commun controle les conditions
    et calcule les scores documentes.

    M1 controle la sortie et refuse toute
    modification de son entree.
    """

    verifier_noyau()

    try:
        course_copie = copy.deepcopy(course)
        course_reference = copy.deepcopy(
            course_copie
        )
    except Exception as erreur:
        raise RuntimeError(
            "Copie de la course impossible"
        ) from erreur

    resultat = noyau_commun.analyser_course(
        course=course_copie,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    try:
        comparaison = (
            course_copie == course_reference
        )
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

def analyser_course_m1(course: Any) -> dict:
    """Point d'entree explicite du moteur M1."""

    return analyser_course(course)


# ============================================================
# 11. CLASSE MOTEUR
# ============================================================

class MoteurM1:
    """Moteur statistique independant."""

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
            "couverture_min": COUVERTURE_MIN,
            "criteres": list(CRITERES),
            "poids": POIDS.copy(),
            "publication": False,
            "fige_automatique": False,
        }


# ============================================================
# 12. AUTOTEST TECHNIQUE
# ============================================================

def self_test() -> bool:
    """
    Controle technique sans donnee PMU.
    Ne produit aucune prediction.
    Ne publie et ne fige rien.
    """

    verifier_noyau()

    moteur = MoteurM1()
    configuration = moteur.configuration()

    if configuration["moteur"] != "M1":
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
            "Autotest : ponderations incorrectes"
        )

    if not callable(moteur.analyser):
        raise RuntimeError(
            "Autotest : analyse indisponible"
        )

    if not callable(analyser_course_m1):
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

    resultat_invalide = {
        "moteur": "M1",
        "version": "2.4",
        "fige": False,
        "publication": False,
        "statut": "DONNEES_INSUFFISANTES",
        "chevaux_analyses": [],
        "classement": [
            {
                "numero": 1,
                "position_predite": 1,
            }
        ],
        "classement_partiel": [],
    }

    try:
        verifier_resultat(
            resultat_invalide
        )
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "Autotest : classement invalide accepte"
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

    return True


# ============================================================
# 13. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Codes de sortie :
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

            print("X1000 V2.4 - M1")
            print("SELF-TEST : OK")
            print("Configuration : conforme")
            print("Noyau : interface compatible")
            print("Criteres : 5")
            print("Ponderations : 20 % chacune")
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
            "ERREUR TECHNIQUE M1 : "
            f"{type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 14. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
