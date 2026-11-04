#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M5 : FIABILITE ET RISQUES

Moteur sportif indépendant.
Aucune collecte PMU.
Aucune publication automatique.
Aucun FIGE automatique.
Aucune écriture d'archives.
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION
# ============================================================

MOTEUR = "M5"
VERSION = "2.4"
CHAMP = "indicateurs_m5"

COUVERTURE_MIN = 0.60
SEUIL_RISQUE = 40.0

POIDS = {
    "fiabilite": 0.25,
    "regularite": 0.20,
    "resistance": 0.15,
    "adaptation_conditions": 0.15,
    "stabilite_performance": 0.15,
    "potentiel_surprise": 0.10,
}

RISQUES = {
    "fiabilite": "Fiabilité sportive faible",
    "regularite": "Irrégularité des performances",
    "resistance": "Résistance insuffisante",
    "adaptation_conditions": "Adaptation incertaine",
    "stabilite_performance": "Stabilité insuffisante",
    "potentiel_surprise": "Potentiel de surprise faible",
}

STATUTS_ATTENDUS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. IMPORT DU NOYAU COMMUN
# ============================================================

noyau_commun = None
ERREUR_IMPORT = None

try:
    if __package__:
        from . import noyau_commun
    else:
        import noyau_commun
except ImportError as erreur:
    ERREUR_IMPORT = erreur


# ============================================================
# 3. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """Accepte uniquement une note finie de 0 à 100."""

    if type(valeur) not in (int, float):
        return None

    try:
        note = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(note):
        return None

    return note if 0 <= note <= 100 else None


# ============================================================
# 4. CONFIGURATION LOCALE
# ============================================================

def verifier_configuration_locale() -> None:

    if MOTEUR != "M5":
        raise RuntimeError("Identité M5 invalide")

    if VERSION != "2.4":
        raise RuntimeError("Version M5 invalide")

    if CHAMP != "indicateurs_m5":
        raise RuntimeError("Champ M5 invalide")

    if set(POIDS) != set(RISQUES):
        raise RuntimeError("Critères M5 incohérents")

    if len(POIDS) != 6:
        raise RuntimeError("Six critères M5 obligatoires")

    for critere, poids in POIDS.items():
        if note_valide(poids) is None or poids <= 0:
            raise RuntimeError(
                f"Poids invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "Somme des pondérations différente de 100 %"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError("Couverture M5 invalide")

    if note_valide(SEUIL_RISQUE) is None:
        raise RuntimeError("Seuil de risque invalide")

    for description in RISQUES.values():
        if not isinstance(description, str):
            raise RuntimeError("Description invalide")
        if not description.strip():
            raise RuntimeError("Description vide")


# ============================================================
# 5. COMPATIBILITE NOYAU
# ============================================================

def verifier_configuration() -> None:

    verifier_configuration_locale()

    if noyau_commun is None:
        raise RuntimeError(
            f"Noyau commun indisponible : {ERREUR_IMPORT}"
        )

    if str(getattr(noyau_commun, "VERSION", None)) != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible"
        )

    for fonction in ("analyser_course", "executer"):
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
            "Statuts du noyau indisponibles"
        )

    if set(statuts) != STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


def verifier_noyau() -> None:
    verifier_configuration()


# ============================================================
# 6. RISQUES DOCUMENTES
# ============================================================

def identifier_risques(criteres: dict) -> list[dict]:

    if not isinstance(criteres, dict):
        raise TypeError("Critères M5 invalides")

    risques_detectes = []

    for critere, description in RISQUES.items():
        note = note_valide(criteres.get(critere))

        if note is not None and note < SEUIL_RISQUE:
            risques_detectes.append({
                "critere": critere,
                "note": note,
                "description": description,
            })

    return risques_detectes


# ============================================================
# 7. PARTANTS ACTIFS
# ============================================================

def construire_partants_actifs(course: Any) -> dict:

    if not isinstance(course, dict):
        raise RuntimeError("Course invalide")

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise RuntimeError("Partants invalides")

    actifs = {}
    numeros = set()

    for cheval in partants:

        if not isinstance(cheval, dict):
            raise RuntimeError("Cheval invalide")

        numero = cheval.get("numero")

        if type(numero) is not int or numero <= 0:
            raise RuntimeError("Numéro invalide")

        if numero in numeros:
            raise RuntimeError("Numéro en double")

        numeros.add(numero)

        non_partant = cheval.get("non_partant")

        if type(non_partant) is not bool:
            raise RuntimeError(
                "Statut non-partant invalide"
            )

        if non_partant:
            continue

        nom = cheval.get("nom")

        if not isinstance(nom, str) or not nom.strip():
            raise RuntimeError("Nom du cheval invalide")

        actifs[numero] = cheval

    return actifs


# ============================================================
# 8. VALIDATION DU RESULTAT
# ============================================================

def verifier_resultat(resultat: Any) -> None:

    if not isinstance(resultat, dict):
        raise RuntimeError("Résultat invalide")

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError("Identité M5 incohérente")

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError("Statut invalide")

    if resultat.get("fige") is not False:
        raise RuntimeError("FIGE interdit")

    if resultat.get("publication") is not False:
        raise RuntimeError("Publication interdite")

    champs = (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    )

    for champ in champs:
        if not isinstance(resultat.get(champ), list):
            raise RuntimeError(
                f"Champ invalide : {champ}"
            )

        if not all(
            isinstance(element, dict)
            for element in resultat[champ]
        ):
            raise RuntimeError(
                f"Entrée invalide : {champ}"
            )

    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]

    if statut == "ANALYSE_DISPONIBLE":
        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":
        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel invalide"
            )

    else:
        if classement or partiel:
            raise RuntimeError(
                "Classement interdit"
            )

    analyses = {}
    scores = {}

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in analyses
        ):
            raise RuntimeError(
                "Numéro analysé invalide"
            )

        score = analyse.get("score")

        if score is not None:
            if note_valide(score) is None:
                raise RuntimeError(
                    "Score analysé invalide"
                )

        if statut != "NON_ANALYSABLE":
            if not isinstance(
                analyse.get("criteres"),
                dict,
            ):
                raise RuntimeError(
                    "Critères M5 manquants"
                )

        analyses[numero] = analyse
        scores[numero] = score

    for champ in ("classement", "classement_partiel"):

        deja_classes = set()

        for rang, position in enumerate(
            resultat[champ],
            start=1,
        ):

            numero = position.get("numero")

            if (
                type(numero) is not int
                or numero not in analyses
                or numero in deja_classes
            ):
                raise RuntimeError(
                    "Numéro classé invalide"
                )

            deja_classes.add(numero)

            if (
                type(position.get("position_predite"))
                is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position prédite invalide"
                )

            score = note_valide(
                position.get("score")
            )

            if score is None:
                raise RuntimeError(
                    "Score de classement invalide"
                )

            if score != scores[numero]:
                raise RuntimeError(
                    "Score de classement incohérent"
                )


# ============================================================
# 9. ENRICHISSEMENT DES ANALYSES
# ============================================================

def enrichir_analyses(resultat: dict) -> None:

    alertes = []
    donnees_manquantes = []

    for analyse in resultat["chevaux_analyses"]:

        criteres = analyse.get("criteres")

        if not isinstance(criteres, dict):
            raise RuntimeError(
                "Critères M5 invalides"
            )

        manquants = [
            critere
            for critere in POIDS
            if note_valide(
                criteres.get(critere)
            ) is None
        ]

        risques = identifier_risques(criteres)

        analyse["score_m5"] = analyse.get("score")
        analyse["risques"] = copy.deepcopy(risques)
        analyse["criteres_manquants"] = manquants

        analyse["admissible"] = (
            analyse.get("score") is not None
        )

        if risques:
            alertes.append({
                "numero": analyse["numero"],
                "nom": analyse.get("nom"),
                "risques": copy.deepcopy(risques),
            })

        if manquants:
            donnees_manquantes.append({
                "numero": analyse["numero"],
                "nom": analyse.get("nom"),
                "criteres_manquants": list(manquants),
            })

    resultat["alertes_risques"] = alertes
    resultat["donnees_manquantes"] = donnees_manquantes


# ============================================================
# 10. ENRICHISSEMENT DES CLASSEMENTS
# ============================================================

def enrichir_classements(resultat: dict) -> None:

    analyses = {
        analyse["numero"]: analyse
        for analyse in resultat["chevaux_analyses"]
    }

    scores = [
        analyse["score"]
        for analyse in analyses.values()
        if analyse.get("score") is not None
    ]

    for champ in ("classement", "classement_partiel"):

        for position in resultat[champ]:

            numero = position["numero"]
            analyse = analyses[numero]
            score = position["score"]

            if score != analyse.get("score"):
                raise RuntimeError(
                    "Score de classement incohérent"
                )

            egalite = (
                sum(
                    autre == score
                    for autre in scores
                ) > 1
            )

            position["score_m5"] = score

            position["risques"] = copy.deepcopy(
                analyse["risques"]
            )

            position["egalite_score"] = egalite


# ============================================================
# 11. ANALYSE INDEPENDANTE M5
# ============================================================

def analyser_course(course: Any) -> dict:

    verifier_configuration()

    course_locale = copy.deepcopy(course)

    resultat_brut = noyau_commun.analyser_course(
        course=course_locale,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat_brut)

    resultat = copy.deepcopy(resultat_brut)

    resultat["alertes_risques"] = []
    resultat["donnees_manquantes"] = []

    # Vérifier les partants avant toute sortie.
    actifs = construire_partants_actifs(course_locale)

    numeros_analyses = {
        analyse["numero"]
        for analyse in resultat["chevaux_analyses"]
    }

    if not numeros_analyses.issubset(set(actifs)):
        raise RuntimeError(
            "Analyse contenant un non-partant "
            "ou un numéro inconnu"
        )

    for analyse in resultat["chevaux_analyses"]:
        cheval = actifs[analyse["numero"]]

        if analyse.get("nom") != cheval.get("nom"):
            raise RuntimeError(
                "Nom du cheval incohérent"
            )

    if resultat["statut"] == "NON_ANALYSABLE":
        resultat["nombre_partants_actifs"] = len(actifs)
        resultat["nombre_chevaux_admissibles"] = 0
        resultat["chevaux_evalues"] = len(
            resultat["chevaux_analyses"]
        )
        return resultat

    if numeros_analyses != set(actifs):
        raise RuntimeError(
            "Tous les partants actifs "
            "doivent être analysés"
        )

    enrichir_analyses(resultat)
    enrichir_classements(resultat)

    resultat["nombre_partants_actifs"] = len(actifs)

    resultat["nombre_chevaux_admissibles"] = sum(
        analyse.get("admissible") is True
        for analyse in resultat["chevaux_analyses"]
    )

    resultat["chevaux_evalues"] = len(
        resultat["chevaux_analyses"]
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 12. INTERFACE X1000
# ============================================================

def analyser_course_m5(course: Any) -> dict:
    return analyser_course(course)


class MoteurM5:

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_configuration()
        return True


# ============================================================
# 13. EXECUTION
# ============================================================

def executer(fonction_analyse=None) -> int:

    verifier_configuration()

    if fonction_analyse is None:
        fonction_analyse = analyser_course

    if not callable(fonction_analyse):
        raise TypeError(
            "Fonction d'analyse invalide"
        )

    code = noyau_commun.executer(fonction_analyse)

    if type(code) is not int:
        raise RuntimeError(
            "Code de sortie invalide"
        )

    return code


# ============================================================
# 14. AUTOTEST
# ============================================================

def self_test() -> int:

    try:
        verifier_configuration()

        if MOTEUR != "M5":
            raise RuntimeError("Identité invalide")

        if VERSION != "2.4":
            raise RuntimeError("Version invalide")

        if len(POIDS) != 6:
            raise RuntimeError("Critères invalides")

        if note_valide(True) is not None:
            raise RuntimeError(
                "Booléen accepté comme note"
            )

        if note_valide(float("nan")) is not None:
            raise RuntimeError(
                "NaN accepté"
            )

        if note_valide(-1) is not None:
            raise RuntimeError(
                "Note négative acceptée"
            )

        if note_valide(101) is not None:
            raise RuntimeError(
                "Note supérieure à 100 acceptée"
            )

        risques = identifier_risques({
            "fiabilite": 30,
            "regularite": 80,
            "resistance": 75,
            "adaptation_conditions": 70,
            "stabilite_performance": 85,
            "potentiel_surprise": 90,
        })

        if len(risques) != 1:
            raise RuntimeError(
                "Détection des risques invalide"
            )

        if risques[0]["critere"] != "fiabilite":
            raise RuntimeError(
                "Risque détecté incorrect"
            )

        if not callable(analyser_course):
            raise RuntimeError(
                "Interface d'analyse absente"
            )

        moteur = MoteurM5()

        if moteur.verifier() is not True:
            raise RuntimeError(
                "Vérification moteur échouée"
            )

        print("X1000 V2.4 — M5")
        print("AUTOTEST : OK")
        print("Moteur : M5")
        print("Critères indépendants : 6")
        print("Pondérations : 100 %")
        print("Couverture minimale : 60 %")
        print("Seuil de risque : 40 / 100")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGE automatique : aucun")
        print("Archives : aucune modification")

        return 0

    except Exception as erreur:

        print(
            f"AUTOTEST M5 : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 15. INTERFACE CLI
# ============================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — M5 Fiabilité et risques",
        add_help=False,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args, _ = parser.parse_known_args()

    if args.self_test:
        return self_test()

    try:
        return executer(analyser_course)

    except Exception as erreur:

        print(
            f"ERREUR M5 : "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 16. POINT D'ENTREE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
