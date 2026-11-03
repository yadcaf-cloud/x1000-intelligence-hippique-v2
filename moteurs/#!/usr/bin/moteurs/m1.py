#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.3 — M1 : statistiques et performances."""

import math
import sys
from collections.abc import Mapping

from base_x1000 import analyser_course, executer

MOTEUR = "M1"
VERSION = "2.3"
CHAMP = "statistiques"
COUVERTURE_MIN = 0.60

POIDS = {
    "forme": 0.25,
    "regularite": 0.20,
    "distance": 0.20,
    "parcours": 0.15,
    "performance": 0.20,
}


def verifier_configuration():
    """Valider la configuration sportive indépendante de M1."""
    if not isinstance(POIDS, dict) or not POIDS:
        raise ValueError("M1 : pondérations absentes")

    for critere, poids in POIDS.items():
        if not isinstance(critere, str) or not critere:
            raise ValueError("M1 : critère invalide")
        if isinstance(poids, bool) or not isinstance(poids, (int, float)):
            raise ValueError(f"M1 : poids non numérique : {critere}")
        if not math.isfinite(poids) or poids <= 0:
            raise ValueError(f"M1 : poids invalide : {critere}")

    if not math.isclose(sum(POIDS.values()), 1.0, abs_tol=1e-9):
        raise ValueError("M1 : la somme des poids doit être égale à 1")

    if not 0 < COUVERTURE_MIN <= 1:
        raise ValueError("M1 : couverture minimale invalide")


def analyser(course):
    """Analyser une course vérifiée via le noyau commun."""
    verifier_configuration()

    if not isinstance(course, Mapping):
        raise ValueError("M1 : course invalide")

    if course.get("localisation_france_verifiee") is not True:
        raise ValueError("M1 : localisation France non vérifiée")

    if course.get("depart_verifie") is not True:
        raise ValueError("M1 : départ non vérifié")

    partants = course.get("partants")
    if not isinstance(partants, list):
        raise ValueError("M1 : liste des partants invalide")

    return analyser_course(
        course=course,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )


class MoteurM1:
    """Interface indépendante du moteur statistique M1."""

    nom = MOTEUR
    version = VERSION

    def analyser(self, course):
        return analyser(course)


if __name__ == "__main__":
    sys.exit(executer(analyser))
  
