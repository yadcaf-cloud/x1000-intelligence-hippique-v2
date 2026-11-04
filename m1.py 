#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M1 : STATISTIQUES ET PERFORMANCES

MISSION
-------
Produire une analyse sportive indépendante M1
sur des données documentées et vérifiées.

CRITÈRES
--------
1. Forme
2. Régularité
3. Distance
4. Parcours
5. Performance

RÈGLES DE SÉCURITÉ
------------------
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

Le noyau commun X1000 V2.4 assure :
- La validation technique des courses.
- Le contrôle des données disponibles.
- Le calcul des scores.
- La production des classements.
- La vérification des sorties.

EXÉCUTION
---------
Depuis la racine du dépôt :

python -m moteurs.m1 --input courses.json

Le fichier d'entrée doit respecter le schéma
attendu par le noyau commun V2.4.
"""

from __future__ import annotations

import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITÉ DU MOTEUR
# ============================================================

MOTEUR = "M1"
VERSION = "2.4"
CHAMP = "statistiques"

# Couverture complète des cinq critères exigée.
COUVERTURE_MIN = 1.0

# Pondérations indépendantes propres à M1.
POIDS = {
    "forme": 0.20,
    "regularite": 0.20,
    "distance": 0.20,
    "parcours": 0.20,
    "performance": 0.20,
}

CRITERES = tuple(POIDS.keys())


# ============================================================
# 2. IMPORT DU NOYAU COMMUN V2.4
# ============================================================

# Compatible avec :
#
# python -m moteurs.m1
#
# et, depuis le dossier moteurs :
#
# python m1.py

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
# 3. CONTRÔLE DE CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    """
    Vérifie la cohérence interne du moteur M1.

    Empêche notamment :
    - Une identité incorrecte.
    - Une couverture invalide.
    - Des pondérations négatives.
    - Des critères manquants.
    - Une somme des poids incohérente.
    """

    if MOTEUR != "M1":
        raise RuntimeError(
            "Identité du moteur M1 incorrecte"
        )

    if VERSION != "2.4":
        raise RuntimeError(
            "Version M1 incompatible"
        )

    if CHAMP != "statistiques":
        raise RuntimeError(
            "Champ statistique incorrect"
        )

    if (
        isinstance(COUVERTURE_MIN, bool)
        or not isinstance(
            COUVERTURE_MIN,
            (int, float),
        )
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Couverture minimale invalide"
        )

    criteres_attendus = {
        "forme",
        "regularite",
        "distance",
        "parcours",
        "performance",
    }

    if set(POIDS) != criteres_attendus:
        raise RuntimeError(
            "Critères statistiques M1 incohérents"
        )

    for critere, poids in POIDS.items():

        if (
            isinstance(poids, bool)
            or not isinstance(poids, (int, float))
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
            "La somme des poids M1 doit être 1"
        )


# ============================================================
# 4. COMPATIBILITÉ DU NOYAU COMMUN
# ============================================================

def verifier_noyau() -> None:
    """
    Vérifie que M1 utilise le noyau V2.4 attendu.

    Refuse toute incompatibilité technique.
    """

    verifier_configuration()

    if str(VERSION_NOYAU) != VERSION:

        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M1={VERSION}, "
            f"noyau={VERSION_NOYAU}"
        )

    if not callable(analyse_commune):
        raise RuntimeError(
            "Analyse commune indisponible"
        )

    if not callable(executer):
        raise RuntimeError(
            "Exécuteur commun indisponible"
        )


# ============================================================
# 5. ANALYSE SPORTIVE INDÉPENDANTE M1
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Produit une analyse statistique indépendante.

    Les cinq critères sont :
    - Forme
    - Régularité
    - Distance
    - Parcours
    - Performance

    Le noyau commun effectue les validations
    techniques et les calculs.

    M1 conserve ses pondérations propres.

    Aucune valeur manquante n'est remplacée
    par une valeur fictive.
    """

    verifier_noyau()

    # Ne pas modifier l'objet source.
    # Le noyau commun doit respecter son
    # contrat de lecture seule.

    resultat = analyse_commune(
        course=course,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Résultat M1 invalide : objet attendu"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identité incorrecte dans le résultat M1"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGÉ non autorisé dans M1"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication non autorisée dans M1"
        )

    statut = resultat.get("statut")

    statuts_autorises = {
        "ANALYSE_DISPONIBLE",
        "DONNEES_INSUFFISANTES",
        "NON_ANALYSABLE",
    }

    if statut not in statuts_autorises:
        raise RuntimeError(
            f"Statut M1 non autorisé : {statut}"
        )

    classement = resultat.get("classement")

    if not isinstance(classement, list):
        raise RuntimeError(
            "Classement M1 invalide"
        )

    if statut != "ANALYSE_DISPONIBLE":

        if classement:
            raise RuntimeError(
                "Classement complet interdit "
                "sans analyse disponible"
            )

    else:

        if len(classement) != 5:
            raise RuntimeError(
                "Une analyse complète M1 doit "
                "contenir cinq positions"
            )

        numeros = []
        positions = []

        for cheval in classement:

            if not isinstance(cheval, dict):
                raise RuntimeError(
                    "Entrée de classement invalide"
                )

            numero = cheval.get("numero")
            position = cheval.get(
                "position_predite"
            )

            if (
                type(numero) is not int
                or numero <= 0
            ):
                raise RuntimeError(
                    "Numéro de cheval invalide"
                )

            if (
                type(position) is not int
                or position not in range(1, 6)
            ):
                raise RuntimeError(
                    "Position prédite invalide"
                )

            numeros.append(numero)
            positions.append(position)

        if len(set(numeros)) != 5:
            raise RuntimeError(
                "Chevaux en double dans M1"
            )

        if positions != [1, 2, 3, 4, 5]:
            raise RuntimeError(
                "Ordre des positions M1 invalide"
            )

    return resultat


# ============================================================
# 6. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m1(course: Any) -> dict:
    """
    Point d'entrée explicite du coordinateur.

    Chaque appel conserve la décision M1
    indépendante des autres moteurs.
    """

    return analyser_course(course)


# ============================================================
# 7. CLASSE MOTEUR M1
# ============================================================

class MoteurM1:
    """
    Interface objet du moteur statistique M1.

    Exemple :

        moteur = MoteurM1()
        resultat = moteur.analyser(course)

    Aucun état sportif n'est partagé
    avec les moteurs M2, M3, M4 ou M5.
    """

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def __init__(self) -> None:

        verifier_noyau()

    def analyser(self, course: Any) -> dict:
        """
        Retourne la décision sportive M1.
        """

        return analyser_course(course)

    def configuration(self) -> dict:
        """
        Retourne une copie de la configuration.

        Aucune modification des paramètres
        internes n'est autorisée par ce retour.
        """

        return {
            "moteur": self.nom,
            "version": self.version,
            "champ": self.champ,
            "couverture_min": COUVERTURE_MIN,
            "criteres": list(CRITERES),
            "poids": POIDS.copy(),
            "publication": False,
            "fige_automatique": False,
        }


# ============================================================
# 8. AUTOTEST DE CONFIGURATION
# ============================================================

def self_test() -> bool:
    """
    Vérifie uniquement la configuration et
    les interfaces techniques de M1.

    Aucun cheval fictif n'est analysé.
    Aucune connexion PMU n'est effectuée.
    Aucun FIGÉ n'est créé.
    Aucun fichier n'est écrit.
    """

    verifier_noyau()

    moteur = MoteurM1()

    configuration = moteur.configuration()

    assert configuration["moteur"] == "M1"
    assert configuration["version"] == "2.4"

    assert len(configuration["criteres"]) == 5

    assert math.isclose(
        math.fsum(configuration["poids"].values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )

    assert callable(moteur.analyser)
    assert callable(analyser_course_m1)

    assert configuration["publication"] is False
    assert configuration["fige_automatique"] is False

    return True


# ============================================================
# 9. EXÉCUTION SÉCURISÉE
# ============================================================

def main() -> int:
    """
    Interface de commande M1.

    Commandes :

    python -m moteurs.m1 --self-test

    python -m moteurs.m1 --input courses.json

    Codes de sortie :
    0 : succès
    1 : erreur technique
    2 : analyse incomplète ou non analysable

    L'exécution normale reste déléguée
    au noyau commun V2.4.
    """

    try:

        if "--self-test" in sys.argv[1:]:

            if sys.argv[1:] != ["--self-test"]:
                print(
                    "Erreur M1 : --self-test doit "
                    "être utilisé seul",
                    file=sys.stderr,
                )
                return 1

            self_test()

            print(
                "X1000 V2.4 — M1 : SELF-TEST OK"
            )

            print(
                "Configuration : conforme"
            )

            print(
                "Noyau commun : compatible"
            )

            print(
                "Publication : désactivée"
            )

            print(
                "FIGÉ automatique : désactivé"
            )

            return 0

        verifier_noyau()

        code = executer(analyser_course)

        if type(code) is not int:
            raise RuntimeError(
                "Code de sortie du noyau invalide"
            )

        if code not in (0, 1, 2):
            raise RuntimeError(
                f"Code de sortie inattendu : {code}"
            )

        return code

    except (
        ImportError,
        RuntimeError,
        ValueError,
        TypeError,
        AssertionError,
        OSError,
    ) as erreur:

        print(
            "ERREUR TECHNIQUE M1 : "
            f"{type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 10. DÉMARRAGE
# ============================================================

if __name__ == "__main__":

    sys.exit(main())
