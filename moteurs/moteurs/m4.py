#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.3 — M4 : analyse tactique indépendante."""

import math
import sys
from collections.abc import Mapping

from base_x1000 import analyser_course, executer

MOTEUR = "M4"
VERSION = "2.3"
CHAMP = "indicateurs_m4"
COUVERTURE_MIN = 0.65

POIDS = {
    "vitesse_depart": 0.15,
    "positionnement": 0.20,
    "adaptation_rythme": 0.20,
    "endurance": 0.20,
    "aptitude_parcours": 0.15,
    "fiabilite_tactique": 0.10,
}


def verifier_configuration():
    """Vérifier la cohérence des paramètres de M4."""
    if not isinstance(POIDS, dict) or not POIDS:
        raise ValueError("M4 : pondérations absentes")

    for critere, poids in POIDS.items():
        if not isinstance(critere, str) or not critere:
            raise ValueError("M4 : critère invalide")

        if isinstance(poids, bool) or not isinstance(poids, (int, float)):
            raise ValueError(f"M4 : poids non numérique : {critere}")

        if not math.isfinite(poids) or poids <= 0:
            raise ValueError(f"M4 : poids invalide : {critere}")

    if not math.isclose(
        sum(POIDS.values()), 1.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("M4 : somme des poids différente de 1")

    if not 0 < COUVERTURE_MIN <= 1:
        raise ValueError("M4 : couverture minimale invalide")


def verifier_course(course):
    """Contrôler les préconditions avant l'analyse tactique."""
    if not isinstance(course, Mapping):
        raise ValueError("M4 : course invalide")

    if course.get("localisation_france_verifiee") is not True:
        raise ValueError("M4 : localisation France non vérifiée")

    if course.get("depart_verifie") is not True:
        raise ValueError("M4 : départ non vérifié")

    if not isinstance(course.get("partants"), list):
        raise ValueError("M4 : liste des partants invalide")


def extraire_risques_tactiques(resultat):
    """Extraire uniquement les risques déjà documentés."""
    chevaux = resultat.get("chevaux_analyses", [])

    if chevaux is None:
        chevaux = []

    if not isinstance(chevaux, list):
        raise ValueError("M4 : chevaux_analyses invalide")

    risques_tactiques = []

    for cheval in chevaux:
        if not isinstance(cheval, Mapping):
            raise ValueError("M4 : cheval analysé invalide")

        risques = cheval.get("risques")

        if risques is None or risques == [] or risques == "":
            continue

        if not isinstance(risques, (list, str)):
            raise ValueError("M4 : format des risques invalide")

        if isinstance(risques, list):
            if not risques:
                continue
            if not all(
                isinstance(risque, str) and risque.strip()
                for risque in risques
            ):
                raise ValueError("M4 : contenu des risques invalide")

        if isinstance(risques, str) and not risques.strip():
            continue

        numero = cheval.get("numero")
        nom = cheval.get("nom")

        if (
            isinstance(numero, bool)
            or not isinstance(numero, int)
            or numero <= 0
            or not isinstance(nom, str)
            or not nom.strip()
        ):
            raise ValueError("M4 : identité du cheval invalide")

        risques_tactiques.append({
            "numero": numero,
            "nom": nom,
            "risques": risques.copy()
            if isinstance(risques, list) else risques,
        })

    return risques_tactiques


def analyser_course_m4(course):
    """Analyser une course avec les critères tactiques de M4."""
    verifier_configuration()
    verifier_course(course)

    resultat = analyser_course(
        course=course,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    if not isinstance(resultat, dict):
        raise ValueError("M4 : résultat du noyau commun invalide")

    risques_tactiques = extraire_risques_tactiques(resultat)

    resultat_final = resultat.copy()
    resultat_final["risques_tactiques"] = risques_tactiques

    return resultat_final


def analyser(course):
    """Interface commune des moteurs X1000."""
    return analyser_course_m4(course)


class MoteurM4:
    """Moteur autonome spécialisé dans l'analyse tactique."""

    nom = MOTEUR
    version = VERSION

    def analyser(self, course):
        return analyser_course_m4(course)


if __name__ == "__main__":
    sys.exit(executer(analyser_course_m4))
