#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M4 : TACTIQUE ET SCENARIOS

MISSION
-------
Analyser les aptitudes tactiques des chevaux
à partir de données sportives documentées.

M4 est indépendant de M1, M2, M3 et M5.

CRITERES
--------
1. Vitesse de départ       : 15 %
2. Positionnement          : 20 %
3. Adaptation au rythme    : 20 %
4. Endurance               : 20 %
5. Aptitude au parcours    : 15 %
6. Fiabilité tactique      : 10 %

SECURITE
--------
- Courses PMU disputées physiquement en France.
- Validation technique par le noyau commun.
- Départ futur et vérifié par le noyau.
- Partants et non-partants contrôlés.
- Cinq positions si données suffisantes.
- Classement partiel si données insuffisantes.
- Aucune donnée sportive inventée.
- Aucune collecte PMU.
- Aucun FIGE automatique ou rétroactif.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucune écriture dans le dépôt.

EXECUTION
---------
python -m moteurs.m4 --self-test
python -m moteurs.m4 --input course.json

Le noyau commun gère les contrôles partagés.
"""

from __future__ import annotations

import argparse
import copy
import math
import sys

from typing import Any, Callable


# ============================================================
# 1. IDENTITE ET CONFIGURATION M4
# ============================================================

MOTEUR = "M4"
VERSION = "2.4"
CHAMP = "indicateurs_m4"

COUVERTURE_MIN = 0.65
SEUIL_RISQUE = 40.0

POIDS = {
    "vitesse_depart": 0.15,
    "positionnement": 0.20,
    "adaptation_rythme": 0.20,
    "endurance": 0.20,
    "aptitude_parcours": 0.15,
    "fiabilite_tactique": 0.10,
}

LIBELLES_RISQUES = {
    "vitesse_depart": "Départ potentiellement difficile",
    "positionnement": "Positionnement défavorable",
    "adaptation_rythme": "Adaptation au rythme incertaine",
    "endurance": "Endurance potentiellement insuffisante",
    "aptitude_parcours": "Aptitude au parcours faible",
    "fiabilite_tactique": "Fiabilité tactique faible",
}

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
    """Vérifie les paramètres sportifs propres à M4."""

    if MOTEUR != "M4":
        raise RuntimeError("Identité M4 invalide")

    if VERSION != "2.4":
        raise RuntimeError("Version M4 invalide")

    if CHAMP != "indicateurs_m4":
        raise RuntimeError("Champ M4 invalide")

    criteres_attendus = {
        "vitesse_depart",
        "positionnement",
        "adaptation_rythme",
        "endurance",
        "aptitude_parcours",
        "fiabilite_tactique",
    }

    if not isinstance(POIDS, dict):
        raise RuntimeError("Pondérations M4 invalides")

    if set(POIDS) != criteres_attendus:
        raise RuntimeError(
            "Les six critères tactiques sont obligatoires"
        )

    for critere, poids in POIDS.items():

        if type(poids) not in (int, float):
            raise RuntimeError(
                f"Poids non numérique : {critere}"
            )

        if not math.isfinite(poids) or poids <= 0:
            raise RuntimeError(
                f"Poids invalide : {critere}"
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

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Couverture minimale M4 invalide"
        )

    if (
        type(SEUIL_RISQUE) not in (int, float)
        or not math.isfinite(SEUIL_RISQUE)
        or not 0 <= SEUIL_RISQUE <= 100
    ):
        raise RuntimeError(
            "Seuil de risque M4 invalide"
        )

    if set(LIBELLES_RISQUES) != set(POIDS):
        raise RuntimeError(
            "Critères de risques incohérents"
        )

    for critere, libelle in LIBELLES_RISQUES.items():
        if not isinstance(libelle, str) or not libelle.strip():
            raise RuntimeError(
                f"Libellé de risque invalide : {critere}"
            )


# ============================================================
# 4. VERIFICATION DU NOYAU COMMUN
# ============================================================

def verifier_configuration() -> None:
    """Contrôle la compatibilité M4 / noyau commun."""

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
            f"M4={VERSION}, noyau={version_noyau}"
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

    statuts_noyau = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if not isinstance(
        statuts_noyau,
        (set, frozenset, tuple, list),
    ):
        raise RuntimeError(
            "Statuts du noyau absents"
        )

    if set(statuts_noyau) != STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


def verifier_noyau() -> None:
    """Alias de compatibilité historique."""
    verifier_configuration()


# ============================================================
# 5. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """Accepte uniquement une note entre 0 et 100."""

    if type(valeur) not in (int, float):
        return None

    try:
        note = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(note):
        return None

    if not 0 <= note <= 100:
        return None

    return note


# ============================================================
# 6. DETECTION DES RISQUES TACTIQUES
# ============================================================

def identifier_risques(criteres: dict) -> list[str]:
    """
    Identifie les fragilités documentées.

    Une donnée absente ou invalide ne devient
    jamais automatiquement un risque.
    """

    if not isinstance(criteres, dict):
        raise TypeError(
            "Les critères tactiques doivent être un dictionnaire"
        )

    risques = []

    for critere, libelle in LIBELLES_RISQUES.items():

        valeur = note_valide(
            criteres.get(critere)
        )

        if valeur is not None and valeur < SEUIL_RISQUE:
            risques.append(libelle)

    return risques


# ============================================================
# 7. VALIDATION DES RESULTATS
# ============================================================

def verifier_resultat(resultat: Any) -> None:
    """Refuse toute sortie incohérente du noyau."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Résultat M4 non conforme"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identité du moteur incohérente"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError("Statut M4 invalide")

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGÉ interdit dans la sortie M4"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans la sortie M4"
        )

    champs = (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    )

    for champ in champs:

        entrees = resultat.get(champ)

        if not isinstance(entrees, list):
            raise RuntimeError(
                f"Champ M4 invalide : {champ}"
            )

        for entree in entrees:
            if not isinstance(entree, dict):
                raise RuntimeError(
                    f"Entrée invalide dans {champ}"
                )

    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M4 obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel incohérent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour course non analysable"
        )

    numeros_analyses = set()

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros_analyses
        ):
            raise RuntimeError(
                "Numéro de cheval analysé invalide"
            )

        numeros_analyses.add(numero)

        score = analyse.get("score")

        if score is not None and note_valide(score) is None:
            raise RuntimeError(
                "Score d'analyse M4 invalide"
            )

        criteres = analyse.get("criteres")

        if statut != "NON_ANALYSABLE":
            if not isinstance(criteres, dict):
                raise RuntimeError(
                    "Critères tactiques manquants"
                )

    for champ in ("classement", "classement_partiel"):

        numeros_classes = set()

        for rang, position in enumerate(
            resultat[champ],
            start=1,
        ):

            numero = position.get("numero")

            if (
                type(numero) is not int
                or numero not in numeros_analyses
                or numero in numeros_classes
            ):
                raise RuntimeError(
                    "Classement M4 incohérent"
                )

            numeros_classes.add(numero)

            if (
                type(position.get("position_predite")) is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position prédite M4 invalide"
                )

            score = note_valide(position.get("score"))

            if score is None:
                raise RuntimeError(
                    "Score de classement M4 invalide"
                )


# ============================================================
# 8. ENRICHISSEMENT DES ANALYSES
# ============================================================

def enrichir_analyses(resultat: dict) -> None:
    """
    Ajoute les alertes tactiques M4.

    Aucun score n'est recalculé.
    Aucune position n'est modifiée.
    """

    risques_tactiques = []

    for analyse in resultat["chevaux_analyses"]:

        criteres = analyse.get("criteres")

        if not isinstance(criteres, dict):
            raise RuntimeError(
                "Critères M4 invalides"
            )

        risques = identifier_risques(criteres)

        analyse["score_m4"] = analyse.get("score")
        analyse["risques"] = list(risques)

        if risques:

            risques_tactiques.append({
                "numero": analyse["numero"],
                "nom": analyse.get("nom"),
                "risques": list(risques),
            })

    resultat["risques_tactiques"] = risques_tactiques

    resultat["alertes_risques"] = copy.deepcopy(
        risques_tactiques
    )


# ============================================================
# 9. ENRICHISSEMENT DU CLASSEMENT
# ============================================================

def enrichir_classement(resultat: dict) -> None:
    """Ajoute les informations tactiques au classement."""

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

            egalite = sum(
                autre_score == score
                for autre_score in scores
            ) > 1

            position["score_m4"] = score

            position["risques"] = list(
                analyse["risques"]
            )

            position["egalite_score"] = egalite


# ============================================================
# 10. ANALYSE SPORTIVE INDEPENDANTE M4
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse tactique indépendante M4.

    Le noyau commun calcule les scores selon
    les six pondérations propres à M4.

    M4 enrichit les résultats sans modifier
    les scores ni les positions prédites.
    """

    verifier_configuration()

    # Protection de la course originale.
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

    resultat["risques_tactiques"] = []
    resultat["alertes_risques"] = []

    if resultat["statut"] == "NON_ANALYSABLE":
        return resultat

    enrichir_analyses(resultat)
    enrichir_classement(resultat)

    resultat["nombre_partants_actifs"] = len(
        resultat["chevaux_analyses"]
    )

    resultat["nombre_chevaux_admissibles"] = sum(
        analyse.get("score") is not None
        for analyse in resultat["chevaux_analyses"]
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 11. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m4(course: Any) -> dict:
    """Point d'entrée explicite du moteur M4."""
    return analyser_course(course)


class MoteurM4:
    """Moteur tactique indépendant M4."""

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_configuration()
        return True


# ============================================================
# 12. EXECUTION COMPATIBLE NOYAU
# ============================================================

def executer(fonction_analyse=None) -> int:
    """Interface historique du moteur M4."""

    verifier_configuration()

    if fonction_analyse is None:
        fonction_analyse = analyser_course

    if not callable(fonction_analyse):
        raise TypeError(
            "Fonction d'analyse M4 invalide"
        )

    code = noyau_commun.executer(fonction_analyse)

    if type(code) is not int:
        raise RuntimeError(
            "Code de sortie du noyau invalide"
        )

    return code


# ============================================================
# 13. AUTOTEST TECHNIQUE M4
# ============================================================

def self_test() -> int:
    """
    Test technique sans données PMU.

    Ne collecte aucune donnée.
    Ne crée aucun FIGÉ.
    Ne publie rien.
    Ne modifie aucune archive.
    """

    try:
        verifier_configuration()

        assert MOTEUR == "M4"
        assert VERSION == "2.4"
        assert CHAMP == "indicateurs_m4"

        assert len(POIDS) == 6

        assert math.isclose(
            math.fsum(POIDS.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

        assert COUVERTURE_MIN == 0.65
        assert SEUIL_RISQUE == 40.0

        assert note_valide(0) == 0.0
        assert note_valide(100) == 100.0

        assert note_valide(-1) is None
        assert note_valide(101) is None
        assert note_valide(float("nan")) is None

        risques = identifier_risques({
            "vitesse_depart": 30,
            "positionnement": 80,
            "adaptation_rythme": 70,
            "endurance": 75,
            "aptitude_parcours": 90,
            "fiabilite_tactique": 85,
        })

        assert len(risques) == 1

        assert risques[0] == LIBELLES_RISQUES[
            "vitesse_depart"
        ]

        assert callable(analyser_course)
        assert callable(analyser_course_m4)

        moteur = MoteurM4()

        assert moteur.nom == MOTEUR
        assert moteur.verifier() is True

        print("X1000 V2.4 — M4")
        print("AUTOTEST : OK")
        print("Moteur : M4")
        print("Spécialité : tactique et scénarios")
        print("Critères indépendants : 6")
        print("Pondérations : 100 %")
        print("Couverture minimale : 65 %")
        print("Seuil de risque : 40 / 100")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Modification archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except Exception as erreur:

        print(
            f"AUTOTEST M4 : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 14. INTERFACE EN LIGNE DE COMMANDE
# ============================================================

def main() -> int:
    """
    Commandes :

    python -m moteurs.m4 --self-test
    python -m moteurs.m4 --input course.json

    L'interface d'analyse est gérée
    par le noyau commun.
    """

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — M4 Tactique et scénarios",
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
            f"ERREUR M4 : "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 15. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
