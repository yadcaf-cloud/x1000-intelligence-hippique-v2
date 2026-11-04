#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.4 — M2 : aptitudes hippiques.

Analyse indépendante sur données documentées, déléguée au noyau commun.
Aucune collecte, donnée inventée, publication, écriture d'archives ou FIGÉ.
"""
from __future__ import annotations

import math
import sys
from typing import Any

if __package__:
    from .noyau_commun import VERSION as VERSION_NOYAU
    from .noyau_commun import analyser_course as analyse_commune
    from .noyau_commun import executer
else:
    from noyau_commun import VERSION as VERSION_NOYAU
    from noyau_commun import analyser_course as analyse_commune
    from noyau_commun import executer

MOTEUR = "M2"
VERSION = "2.4"
CHAMP = "aptitudes"
COUVERTURE_MIN = 0.60

POIDS = {
    "forme": 0.25,
    "distance": 0.25,
    "terrain": 0.15,
    "discipline": 0.20,
    "regularite": 0.15,
}


def verifier_configuration() -> None:
    """Refuse une configuration locale ou une interface noyau incompatible."""
    if str(VERSION_NOYAU) != VERSION:
        raise RuntimeError(
            f"Version du noyau incompatible : M2={VERSION}, noyau={VERSION_NOYAU}"
        )
    if not callable(analyse_commune) or not callable(executer):
        raise RuntimeError("Interface du noyau commun invalide")
    if not POIDS or any(
        not isinstance(critere, str)
        or not critere.strip()
        or isinstance(poids, bool)
        or not isinstance(poids, (int, float))
        or not math.isfinite(poids)
        or poids <= 0
        for critere, poids in POIDS.items()
    ):
        raise ValueError("Pondérations M2 invalides")
    if not math.isclose(sum(POIDS.values()), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("La somme des pondérations M2 doit être égale à 1")
    if (
        isinstance(COUVERTURE_MIN, bool)
        or not isinstance(COUVERTURE_MIN, (int, float))
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise ValueError("Seuil de couverture M2 invalide")
    if not isinstance(CHAMP, str) or not CHAMP.strip():
        raise ValueError("Champ M2 invalide")


def verifier_noyau() -> None:
    """Alias historique pour les intégrations existantes."""
    verifier_configuration()


def analyser_course(course: Any) -> dict:
    """Délègue l'analyse au noyau avec les paramètres propres à M2."""
    verifier_configuration()
    return analyse_commune(course, MOTEUR, POIDS, CHAMP, COUVERTURE_MIN)


def analyser_course_m2(course: Any) -> dict:
    """Point d'entrée explicite du coordinateur X1000."""
    return analyser_course(course)


class MoteurM2:
    """Interface objet du moteur M2."""

    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)


def main() -> int:
    """Lance l'interface en ligne de commande fournie par le noyau."""
    verifier_configuration()
    return executer(analyser_course)


if __name__ == "__main__":
    sys.exit(main())
