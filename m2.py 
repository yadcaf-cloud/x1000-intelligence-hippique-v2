#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M2 : APTITUDES HIPPIQUES

MISSION
-------
Analyser indépendamment les aptitudes des chevaux
à partir de données sportives documentées.

CRITÈRES
--------
1. Forme       : 25 %
2. Distance    : 25 %
3. Terrain     : 15 %
4. Discipline  : 20 %
5. Régularité  : 15 %

SÉCURITÉ
--------
- Courses PMU françaises uniquement, vérifiées en amont.
- Départ futur et vérifié par le noyau commun.
- Partants et non-partants contrôlés par le noyau.
- Aucune donnée sportive inventée.
- Aucune prédiction sans données suffisantes.
- Aucun FIGÉ automatique ou rétroactif.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucune écriture dans les archives.
- Aucune modification du dépôt.

ARCHITECTURE
------------
M2 conserve ses propres critères et pondérations.

Le noyau commun X1000 V2.4 assure les validations
partagées et l'exécution des analyses.

Les cinq moteurs M1 à M5 restent indépendants.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable

# ============================================================
# 1. CONFIGURATION INDÉPENDANTE M2
# ============================================================

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

# ============================================================
# 2. IMPORT CONTRÔLÉ DU NOYAU COMMUN
# ============================================================

VERSION_NOYAU: Any = None
analyse_commune: Any = None
executer: Any = None
ERREUR_IMPORT: Exception | None = None

try:
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
except (ImportError, ModuleNotFoundError) as exc:
    ERREUR_IMPORT = exc


# ============================================================
# 3. VALIDATION LOCALE DES PONDÉRATIONS
# ============================================================

def verifier_ponderations() -> None:
    """Vérifie les paramètres sportifs indépendants de M2."""

    if not isinstance(MOTEUR, str) or MOTEUR != "M2":
        raise ValueError("Identifiant M2 invalide")

    if not isinstance(VERSION, str) or not VERSION.strip():
        raise ValueError("Version M2 invalide")

    if not isinstance(CHAMP, str) or not CHAMP.strip():
        raise ValueError("Champ M2 invalide")

    if not isinstance(POIDS, dict) or not POIDS:
        raise ValueError("Pondérations M2 absentes")

    criteres_attendus = {
        "forme",
        "distance",
        "terrain",
        "discipline",
        "regularite",
    }

    if set(POIDS) != criteres_attendus:
        raise ValueError(
            "Les cinq critères sportifs M2 sont obligatoires"
        )

    for critere, poids in POIDS.items():

        if not isinstance(critere, str) or not critere.strip():
            raise ValueError("Critère M2 invalide")

        if isinstance(poids, bool):
            raise ValueError(
                f"Pondération booléenne interdite : {critere}"
            )

        if not isinstance(poids, (int, float)):
            raise ValueError(
                f"Pondération non numérique : {critere}"
            )

        if not math.isfinite(poids) or poids <= 0:
            raise ValueError(
                f"Pondération invalide : {critere}"
            )

    total = math.fsum(POIDS.values())

    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"Somme des pondérations invalide : {total}"
        )

    if isinstance(COUVERTURE_MIN, bool):
        raise ValueError("Couverture booléenne interdite")

    if not isinstance(COUVERTURE_MIN, (int, float)):
        raise ValueError("Couverture non numérique")

    if not math.isfinite(COUVERTURE_MIN):
        raise ValueError("Couverture non finie")

    if not 0 < COUVERTURE_MIN <= 1:
        raise ValueError("Couverture hors limites")


# ============================================================
# 4. VÉRIFICATION DU NOYAU COMMUN
# ============================================================

def verifier_configuration() -> None:
    """Contrôle la compatibilité technique M2 / noyau."""

    verifier_ponderations()

    if ERREUR_IMPORT is not None:
        raise RuntimeError(
            "Impossible de charger noyau_commun.py : "
            f"{ERREUR_IMPORT}"
        ) from ERREUR_IMPORT

    if str(VERSION_NOYAU) != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M2={VERSION}, noyau={VERSION_NOYAU}"
        )

    if not callable(analyse_commune):
        raise RuntimeError(
            "Fonction analyser_course absente du noyau"
        )

    if not callable(executer):
        raise RuntimeError(
            "Fonction executer absente du noyau"
        )


def verifier_noyau() -> None:
    """Alias historique pour les intégrations X1000."""
    verifier_configuration()


# ============================================================
# 5. ANALYSE SPORTIVE INDÉPENDANTE M2
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Transmet une course au noyau commun.

    Les décisions sportives utilisent exclusivement
    les paramètres indépendants de M2.

    Les contrôles de validité des courses, des partants,
    des horaires et des données relèvent du noyau.
    """

    verifier_configuration()

    resultat = analyse_commune(
        course,
        MOTEUR,
        POIDS.copy(),
        CHAMP,
        COUVERTURE_MIN,
    )

    if not isinstance(resultat, dict):
        raise TypeError(
            "Le noyau doit retourner un dictionnaire"
        )

    return resultat


def analyser_course_m2(course: Any) -> dict:
    """Point d'entrée explicite du coordinateur X1000."""
    return analyser_course(course)


# ============================================================
# 6. INTERFACE OBJET M2
# ============================================================

class MoteurM2:
    """Moteur autonome M2 — aptitudes hippiques."""

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_configuration()
        return True


# ============================================================
# 7. AUTOTEST TECHNIQUE SANS DONNÉES PMU
# ============================================================

def self_test() -> int:
    """
    Vérifie la configuration et l'interface M2.

    Ne collecte aucune donnée.
    Ne crée aucune prédiction.
    Ne modifie aucun fichier.
    Ne déclenche aucun FIGÉ.
    """

    try:
        verifier_ponderations()

        assert MOTEUR == "M2"
        assert VERSION == "2.4"
        assert CHAMP == "aptitudes"

        assert len(POIDS) == 5

        assert math.isclose(
            math.fsum(POIDS.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

        assert COUVERTURE_MIN == 0.60

        assert callable(analyser_course)
        assert callable(analyser_course_m2)

        moteur = MoteurM2()

        assert moteur.nom == MOTEUR
        assert moteur.version == VERSION
        assert callable(moteur.analyser)

        verifier_configuration()

        print("X1000 V2.4 — M2")
        print("AUTOTEST : OK")
        print("Moteur : M2")
        print("Spécialité : aptitudes hippiques")
        print("Critères : 5")
        print("Pondérations : 100 %")
        print("Couverture minimale : 60 %")
        print(f"Noyau commun : {VERSION_NOYAU}")
        print("Collecte PMU : désactivée")
        print("Publication : désactivée")
        print("FIGÉ automatique : désactivé")
        print("Écriture archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except (AssertionError, Exception) as exc:
        print(
            f"AUTOTEST M2 : ÉCHEC — "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


# ============================================================
# 8. EXÉCUTION EN LIGNE DE COMMANDE
# ============================================================

def main() -> int:
    """Interface CLI compatible avec le noyau commun."""

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — M2 Aptitudes hippiques",
        add_help=False,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Vérifier M2 sans analyser de course",
    )

    args, _ = parser.parse_known_args()

    if args.self_test:
        return self_test()

    try:
        verifier_configuration()

        resultat = executer(analyser_course)

        if isinstance(resultat, bool):
            raise TypeError(
                "Le noyau doit retourner un code entier, "
                "pas un booléen"
            )

        if not isinstance(resultat, int):
            raise TypeError(
                "Le noyau doit retourner un code de sortie entier"
            )

        return resultat

    except Exception as exc:
        print(
            f"ERREUR M2 : {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


# ============================================================
# 9. POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
