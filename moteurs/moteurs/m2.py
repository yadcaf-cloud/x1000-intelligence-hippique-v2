#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.3 — M2 : aptitudes hippiques."""

import math
import sys
from collections.abc import Mapping

from base_x1000 import analyser_course, executer

MOTEUR = "M2"
VERSION = "2.3"
CHAMP = "aptitudes"
COUVERTURE_MIN = 0.60

POIDS = {
    "forme": 0.25,
    "distance": 0.25,
    "terrain": 0.15,
    "discipline": 0.20,
    "regularite": 0.15,
}


def verifier_configuration():
    """Valider les pondérations indépendantes de M2."""
    if not isinstance(POIDS, dict) or not POIDS:
        raise ValueError("M2 : pondérations absentes")

    for critere, poids in POIDS.items():
        if not isinstance(critere, str) or not critere:
            raise ValueError("M2 : critère invalide")
        if isinstance(poids, bool) or not isinstance(poids, (int, float)):
            raise ValueError(f"M2 : poids non numérique : {critere}")
        if not math.isfinite(poids) or poids <= 0:
            raise ValueError(f"M2 : poids invalide : {critere}")

    if not math.isclose(
        sum(POIDS.values()), 1.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("M2 : somme des poids différente de 1")

    if not 0 < COUVERTURE_MIN <= 1:
        raise ValueError("M2 : couverture minimale invalide")


def analyser_course_m2(course):
    """Analyser les aptitudes des chevaux avec M2."""
    verifier_configuration()

    if not isinstance(course, Mapping):
        raise ValueError("M2 : course invalide")

    if course.get("localisation_france_verifiee") is not True:
        raise ValueError("M2 : localisation France non vérifiée")

    if course.get("depart_verifie") is not True:
        raise ValueError("M2 : départ non vérifié")

    if not isinstance(course.get("partants"), list):
        raise ValueError("M2 : liste des partants invalide")

    return analyser_course(
        course=course,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )


def analyser_course_v2(course):
    """Compatibilité avec les anciens appels."""
    return analyser_course_m2(course)


def analyser(course):
    """Interface commune des moteurs X1000."""
    return analyser_course_m2(course)


class MoteurM2:
    """Moteur indépendant spécialisé dans les aptitudes."""

    nom = MOTEUR
    version = VERSION

    def analyser(self, course):
        return analyser_course_m2(course)


if __name__ == "__main__":
    sys.exit(executer(analyser_course_m2))
