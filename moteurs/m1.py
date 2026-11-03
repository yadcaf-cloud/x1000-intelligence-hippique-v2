#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M1 : STATISTIQUES ET PERFORMANCES

Decision sportive independante sur donnees documentees.

Criteres :
- Forme
- Regularite
- Distance
- Parcours
- Performance

Securite :
- Courses PMU en France verifiees en amont.
- Depart verifie et non encore passe.
- Partants et non-partants controles.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune modification des archives.

Les validations techniques sont deleguees
au noyau commun X1000 V2.4.
"""

from __future__ import annotations

import sys
from typing import Any

# ============================================================
# 1. IMPORT DU NOYAU COMMUN
# ============================================================

if __package__:
    from .noyau_commun import (
        VERSION as VERSION_NOYAU,
        analyser_course as analyse_commune,
        executer,
    )
else:
    from noyau_commun import (
        VERSION as VERSION_NOYAU,
        analyser_course as analyse_commune,
        executer,
    )


# ============================================================
# 2. IDENTITE ET CONFIGURATION
# ============================================================

MOTEUR = "M1"
VERSION = "2.4"
CHAMP = "statistiques"

COUVERTURE_MIN = 1.0

POIDS = {
    "forme": 0.20,
    "regularite": 0.20,
    "distance": 0.20,
    "parcours": 0.20,
    "performance": 0.20,
}


# ============================================================
# 3. COMPATIBILITE DU NOYAU
# ============================================================

def verifier_noyau() -> None:
    """
    Refuse une version incompatible du noyau commun.
    """

    if VERSION_NOYAU != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M1={VERSION}, noyau={VERSION_NOYAU}"
        )


# ============================================================
# 4. ANALYSE SPORTIVE M1
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse statistique independante du moteur M1.

    Le noyau commun effectue les controles techniques
    et calcule le classement a partir des ponderations
    propres au moteur M1.

    Aucun classement n'est invente lorsque les
    indicateurs sont absents ou insuffisants.
    """

    verifier_noyau()

    return analyse_commune(
        course=course,
        moteur=MOTEUR,
        poids=POIDS,
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )


# ============================================================
# 5. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m1(course: Any) -> dict:
    """
    Point d'entree explicite pour X1000.
    """

    return analyser_course(course)


# ============================================================
# 6. CLASSE MOTEUR M1
# ============================================================

class MoteurM1:
    """
    Moteur M1 autonome dans ses choix statistiques.

    Exemple :
        moteur = MoteurM1()
        resultat = moteur.analyser(course)
    """

    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        """
        Retourne la decision sportive M1.
        """

        return analyser_course(course)


# ============================================================
# 7. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Execution en lecture seule.

    Commande :
        python -m moteurs.m1 --input course.json

    Codes de sortie :
        0 : analyse complete disponible
        2 : analyse incomplete ou course non analysable
        1 : erreur technique
    """

    verifier_noyau()

    return executer(analyser_course)


# ============================================================
# 8. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
