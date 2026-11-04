#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M1 : STATISTIQUES ET PERFORMANCES

MISSION
-------
Produire une analyse sportive indépendante M1
sur des données documentées et vérifiées en amont.

CRITERES
--------
1. Forme
2. Régularité
3. Distance
4. Parcours
5. Performance

PONDERATIONS
------------
Chaque critère représente 20 % du score.

Couverture minimale : 100 %.

SECURITE
--------
- Courses PMU physiquement disputées en France.
- Départ vérifié et obligatoirement futur.
- Partants et non-partants contrôlés.
- Aucune donnée sportive inventée.
- Aucune prédiction complète sans données suffisantes.
- Aucun FIGÉ automatique ou rétroactif.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucune écriture dans le dépôt.

ARCHITECTURE
------------
M1 conserve ses propres critères et pondérations.

Le noyau commun X1000 V2.4 assure les validations
techniques et le calcul des scores.

COMMANDES
---------
python -m moteurs.m1 --self-test
python -m moteurs.m1 --input course.json
"""

from __future__ import annotations

import argparse
import copy
import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION M1
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

CRITERES_ATTENDUS = frozenset({
    "forme",
    "regularite",
    "distance",
    "parcours",
    "performance",
})

STATUTS_ATTENDUS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. IMPORT CONTROLE DU NOYAU COMMUN
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
# 3. VALIDATION DE LA CONFIGURATION LOCALE
# ============================================================

def verifier_configuration_locale() -> None:
    """Contrôle les paramètres sportifs propres à M1."""

    if MOTEUR != "M1":
        raise RuntimeError("Identité M1 invalide")

    if VERSION != "2.4":
        raise RuntimeError("Version M1 invalide")

    if CHAMP != "statistiques":
        raise RuntimeError("Champ statistique M1 invalide")

    if not isinstance(POIDS, dict):
        raise RuntimeError("Pondérations M1 invalides")

    if set(POIDS) != CRITERES_ATTENDUS:
        raise RuntimeError(
            "Les cinq critères statistiques sont obligatoires"
        )

    for critere, poids in POIDS.items():

        if type(poids) not in (int, float):
            raise RuntimeError(
                f"Pondération non numérique : {critere}"
            )

        if not math.isfinite(poids) or poids <= 0:
            raise RuntimeError(
                f"Pondération invalide : {critere}"
            )

    total = math.fsum(POIDS.values())

    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            f"Somme des pondérations invalide : {total}"
        )

    if any(
        not math.isclose(
            poids,
            0.20,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for poids in POIDS.values()
    ):
        raise RuntimeError(
            "Chaque critère M1 doit peser 20 %"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or COUVERTURE_MIN != 1.0
    ):
        raise RuntimeError(
            "Couverture minimale M1 invalide"
        )


# ============================================================
# 4. VERIFICATION DU NOYAU COMMUN
# ============================================================

def verifier_noyau() -> None:
    """Vérifie la compatibilité technique M1 / noyau."""

    verifier_configuration_locale()

    if noyau_commun is None:
        raise RuntimeError(
            "Noyau commun indisponible : "
            f"{ERREUR_IMPORT}"
        )

    version_noyau = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if str(version_noyau) != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M1={VERSION}, noyau={version_noyau}"
        )

    if not callable(
        getattr(noyau_commun, "analyser_course", None)
    ):
        raise RuntimeError(
            "Fonction analyser_course indisponible"
        )

    if not callable(
        getattr(noyau_commun, "executer", None)
    ):
        raise RuntimeError(
            "Fonction executer indisponible"
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

    if set(statuts) != STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


def verifier_configuration() -> None:
    """Alias de compatibilité avec les autres moteurs."""
    verifier_noyau()


# ============================================================
# 5. VALIDATION DU RESULTAT M1
# ============================================================

def verifier_resultat(resultat: Any) -> None:
    """Contrôle les résultats retournés par le noyau."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Résultat M1 non conforme"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identité du moteur incohérente"
        )

    if str(resultat.get("version")) != VERSION:
        raise RuntimeError(
            "Version du résultat incompatible"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statut M1 invalide"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGÉ interdit dans la sortie M1"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans la sortie M1"
        )

    for champ in (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    ):

        if not isinstance(resultat.get(champ), list):
            raise RuntimeError(
                f"Champ M1 invalide : {champ}"
            )

    analyses = resultat["chevaux_analyses"]
    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]

    numeros_analyses = set()
    scores = {}

    for analyse in analyses:

        if not isinstance(analyse, dict):
            raise RuntimeError(
                "Analyse de cheval invalide"
            )

        numero = analyse.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros_analyses
        ):
            raise RuntimeError(
                "Numéro analysé M1 invalide"
            )

        numeros_analyses.add(numero)

        score = analyse.get("score")

        if score is not None:
            if noyau_commun.note_valide(score) is None:
                raise RuntimeError(
                    "Score M1 invalide"
                )

        scores[numero] = score

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M1 obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel M1 incohérent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour course non analysable"
        )

    for champ in ("classement", "classement_partiel"):

        numeros_classes = set()

        for rang, position in enumerate(
            resultat[champ],
            start=1,
        ):

            if not isinstance(position, dict):
                raise RuntimeError(
                    "Position M1 invalide"
                )

            numero = position.get("numero")

            if (
                type(numero) is not int
                or numero not in numeros_analyses
                or numero in numeros_classes
            ):
                raise RuntimeError(
                    "Classement M1 incohérent"
                )

            numeros_classes.add(numero)

            if (
                type(position.get("position_predite")) is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position prédite M1 invalide"
                )

            score = noyau_commun.note_valide(
                position.get("score")
            )

            if score is None:
                raise RuntimeError(
                    "Score de classement M1 invalide"
                )

            if score != scores[numero]:
                raise RuntimeError(
                    "Score de classement incohérent"
                )


# ============================================================
# 6. ANALYSE SPORTIVE INDEPENDANTE M1
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse statistique indépendante M1.

    Les cinq critères sont obligatoires
    pour obtenir un score admissible.

    Aucun score ou classement n'est inventé.
    """

    verifier_noyau()

    # Protection des données originales.
    course_locale = copy.deepcopy(course)

    resultat_brut = noyau_commun.analyser_course(
        course=course_locale,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat_brut)

    # Protection du résultat original du noyau.
    resultat = copy.deepcopy(resultat_brut)

    return resultat


# ============================================================
# 7. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m1(course: Any) -> dict:
    """Point d'entrée explicite du moteur M1."""
    return analyser_course(course)


# ============================================================
# 8. CLASSE MOTEUR M1
# ============================================================

class MoteurM1:
    """Moteur statistique indépendant M1."""

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_noyau()
        return True


# ============================================================
# 9. AUTOTEST TECHNIQUE M1
# ============================================================

def self_test() -> int:
    """
    Test de configuration sans données PMU.

    Aucun téléchargement.
    Aucune analyse de course réelle.
    Aucun FIGÉ.
    Aucune publication.
    Aucune modification d'archives.
    """

    try:
        verifier_noyau()

        assert MOTEUR == "M1"
        assert VERSION == "2.4"
        assert CHAMP == "statistiques"

        assert len(POIDS) == 5

        assert math.isclose(
            math.fsum(POIDS.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

        assert all(
            poids == 0.20
            for poids in POIDS.values()
        )

        assert COUVERTURE_MIN == 1.0

        assert callable(analyser_course)
        assert callable(analyser_course_m1)

        moteur = MoteurM1()

        assert moteur.nom == MOTEUR
        assert moteur.verifier() is True

        print("X1000 V2.4 — M1")
        print("AUTOTEST : OK")
        print("Moteur : M1")
        print("Spécialité : statistiques et performances")
        print("Critères indépendants : 5")
        print("Pondérations : 20 % par critère")
        print("Couverture minimale : 100 %")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Modification archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except Exception as erreur:

        print(
            f"AUTOTEST M1 : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 10. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Commandes :

    python -m moteurs.m1 --self-test
    python -m moteurs.m1 --input course.json

    Codes de sortie :
    0 : analyse complète disponible
    2 : données insuffisantes ou non analysable
    1 : erreur technique
    """

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — M1 Statistiques",
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
        verifier_noyau()

        code = noyau_commun.executer(
            analyser_course
        )

        if type(code) is not int:
            raise RuntimeError(
                "Code de sortie du noyau invalide"
            )

        return code

    except Exception as erreur:

        print(
            f"ERREUR M1 : "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 11. POINT D'ENTREE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
