#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M5 : FIABILITE ET RISQUES

MISSION
-------
Moteur sportif indépendant M5.

- Étudier chaque cheval actif.
- Évaluer fiabilité, régularité et résistance.
- Analyser adaptation et stabilité.
- Examiner le potentiel de surprise.
- Identifier les risques documentés.
- Produire cinq positions si les données suffisent.
- Conserver les classements partiels.

CRITERES
--------
Fiabilité              : 25 %
Régularité             : 20 %
Résistance             : 15 %
Adaptation conditions  : 15 %
Stabilité performance  : 15 %
Potentiel surprise     : 10 %

SECURITE
--------
- Courses PMU disputées physiquement en France.
- Validation technique déléguée au noyau commun.
- Départ futur et vérifié par le noyau.
- Aucun non-partant dans les classements.
- Aucune donnée sportive inventée.
- Aucune collecte PMU.
- Aucun FIGÉ automatique ou rétroactif.
- Aucune publication.
- Aucune écriture d'archives.
- Aucune modification du dépôt.

EXECUTION
---------
python -m moteurs.m5 --self-test
python -m moteurs.m5 --input course.json
"""

from __future__ import annotations

import argparse
import copy
import math
import sys

from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION M5
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
# 3. VALIDATION CONFIGURATION LOCALE
# ============================================================

def verifier_configuration_locale() -> None:
    """Vérifie les paramètres sportifs indépendants M5."""

    if MOTEUR != "M5":
        raise RuntimeError("Identité M5 invalide")

    if VERSION != "2.4":
        raise RuntimeError("Version M5 invalide")

    if CHAMP != "indicateurs_m5":
        raise RuntimeError("Champ M5 invalide")

    criteres_attendus = {
        "fiabilite",
        "regularite",
        "resistance",
        "adaptation_conditions",
        "stabilite_performance",
        "potentiel_surprise",
    }

    if not isinstance(POIDS, dict):
        raise RuntimeError("Pondérations M5 invalides")

    if set(POIDS) != criteres_attendus:
        raise RuntimeError(
            "Les six critères M5 sont obligatoires"
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
            f"Somme des pondérations M5 invalide : {total}"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Couverture minimale M5 invalide"
        )

    if (
        type(SEUIL_RISQUE) not in (int, float)
        or not math.isfinite(SEUIL_RISQUE)
        or not 0 <= SEUIL_RISQUE <= 100
    ):
        raise RuntimeError(
            "Seuil de risque M5 invalide"
        )

    if set(RISQUES) != set(POIDS):
        raise RuntimeError(
            "Critères de risques M5 incohérents"
        )

    for critere, description in RISQUES.items():

        if (
            not isinstance(description, str)
            or not description.strip()
        ):
            raise RuntimeError(
                f"Description de risque invalide : {critere}"
            )


# ============================================================
# 4. VERIFICATION DU NOYAU COMMUN
# ============================================================

def verifier_configuration() -> None:
    """Contrôle la compatibilité M5 / noyau commun."""

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
            f"M5={VERSION}, noyau={version_noyau}"
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
    """Alias historique de compatibilité."""
    verifier_configuration()


# ============================================================
# 5. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """Accepte une note numérique finie entre 0 et 100."""

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
# 6. IDENTIFICATION DES RISQUES M5
# ============================================================

def identifier_risques(criteres: dict) -> list[dict]:
    """
    Identifie uniquement les risques documentés.

    Une donnée absente ne devient jamais
    une note fictive ou un risque automatique.
    """

    if not isinstance(criteres, dict):
        raise TypeError(
            "Les critères M5 doivent être un dictionnaire"
        )

    risques_detectes = []

    for critere, description in RISQUES.items():

        note = note_valide(
            criteres.get(critere)
        )

        if note is not None and note < SEUIL_RISQUE:

            risques_detectes.append({
                "critere": critere,
                "note": note,
                "description": description,
            })

    return risques_detectes


# ============================================================
# 7. VALIDATION DES PARTANTS ACTIFS
# ============================================================

def construire_partants_actifs(course: Any) -> dict:
    """Contrôle les numéros et les non-partants."""

    if not isinstance(course, dict):
        raise RuntimeError("Course M5 invalide")

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise RuntimeError("Liste des partants invalide")

    actifs = {}
    numeros = set()

    for cheval in partants:

        if not isinstance(cheval, dict):
            raise RuntimeError(
                "Entrée de cheval invalide"
            )

        numero = cheval.get("numero")

        if type(numero) is not int or numero <= 0:
            raise RuntimeError(
                "Numéro de cheval invalide"
            )

        if numero in numeros:
            raise RuntimeError(
                "Numéro de cheval en double"
            )

        numeros.add(numero)

        if type(cheval.get("non_partant")) is not bool:
            raise RuntimeError(
                "Statut non-partant invalide"
            )

        if not cheval["non_partant"]:

            nom = cheval.get("nom")

            if (
                not isinstance(nom, str)
                or not nom.strip()
            ):
                raise RuntimeError(
                    "Nom du partant invalide"
                )

            actifs[numero] = cheval

    return actifs


# ============================================================
# 8. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(resultat: Any) -> None:
    """Refuse toute sortie incohérente du noyau."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Résultat M5 non conforme"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identité du moteur incohérente"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statut M5 invalide"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGÉ interdit dans la sortie M5"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans la sortie M5"
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
                f"Champ M5 invalide : {champ}"
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
                "Cinq positions M5 obligatoires"
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
                "Numéro analysé M5 invalide"
            )

        numeros_analyses.add(numero)

        score = analyse.get("score")

        if score is not None and note_valide(score) is None:
            raise RuntimeError(
                "Score d'analyse M5 invalide"
            )

        if statut != "NON_ANALYSABLE":
            if not isinstance(analyse.get("criteres"), dict):
                raise RuntimeError(
                    "Critères M5 manquants"
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
                    "Classement M5 incohérent"
                )

            numeros_classes.add(numero)

            if (
                type(position.get("position_predite")) is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position prédite M5 invalide"
                )

            if note_valide(position.get("score")) is None:
                raise RuntimeError(
                    "Score de classement M5 invalide"
                )


# ============================================================
# 9. ENRICHISSEMENT DES ANALYSES M5
# ============================================================

def enrichir_analyses(resultat: dict) -> None:
    """
    Ajoute risques et données manquantes.

    Aucun score n'est recalculé ou inventé.
    """

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
            if note_valide(criteres.get(critere)) is None
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
    """Ajoute les informations M5 aux positions."""

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

            egalite = sum(
                autre_score == score
                for autre_score in scores
            ) > 1

            position["score_m5"] = score

            position["risques"] = copy.deepcopy(
                analyse["risques"]
            )

            position["egalite_score"] = egalite


# ============================================================
# 11. ANALYSE SPORTIVE INDEPENDANTE M5
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Décision sportive indépendante M5.

    Le noyau commun valide les données et
    calcule les scores avec les pondérations M5.

    M5 enrichit ensuite les résultats sans
    modifier les scores ou les positions.
    """

    verifier_configuration()

    # Protection des données d'entrée.
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

    resultat["alertes_risques"] = []
    resultat["donnees_manquantes"] = []

    if resultat["statut"] == "NON_ANALYSABLE":
        resultat["nombre_partants_actifs"] = 0
        resultat["nombre_chevaux_admissibles"] = 0
        resultat["chevaux_evalues"] = 0
        return resultat

    actifs = construire_partants_actifs(course_locale)

    numeros_analyses = {
        analyse["numero"]
        for analyse in resultat["chevaux_analyses"]
    }

    if numeros_analyses != set(actifs):
        raise RuntimeError(
            "Les analyses ne correspondent pas "
            "aux partants actifs"
        )

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse["numero"]
        cheval = actifs[numero]

        if analyse.get("nom") != cheval.get("nom"):
            raise RuntimeError(
                "Nom du cheval incohérent"
            )

    enrichir_analyses(resultat)
    enrichir_classements(resultat)

    resultat["nombre_partants_actifs"] = len(actifs)

    resultat["nombre_chevaux_admissibles"] = sum(
        analyse.get("score") is not None
        for analyse in resultat["chevaux_analyses"]
    )

    resultat["chevaux_evalues"] = len(
        resultat["chevaux_analyses"]
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 12. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m5(course: Any) -> dict:
    """Point d'entrée explicite du moteur M5."""
    return analyser_course(course)


class MoteurM5:
    """Moteur indépendant M5 — fiabilité et risques."""

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_configuration()
        return True


# ============================================================
# 13. EXECUTION COMPATIBLE NOYAU
# ============================================================

def executer(fonction_analyse=None) -> int:
    """Interface historique compatible."""

    verifier_configuration()

    if fonction_analyse is None:
        fonction_analyse = analyser_course

    if not callable(fonction_analyse):
        raise TypeError(
            "Fonction d'analyse M5 invalide"
        )

    code = noyau_commun.executer(fonction_analyse)

    if type(code) is not int:
        raise RuntimeError(
            "Code de sortie du noyau invalide"
        )

    return code


# ============================================================
# 14. AUTOTEST TECHNIQUE M5
# ============================================================

def self_test() -> int:
    """
    Vérification technique sans données PMU.

    Aucun téléchargement.
    Aucune analyse réelle.
    Aucun FIGÉ.
    Aucune publication.
    Aucune modification d'archives.
    """

    try:
        verifier_configuration()

        assert MOTEUR == "M5"
        assert VERSION == "2.4"
        assert CHAMP == "indicateurs_m5"

        assert len(POIDS) == 6

        assert math.isclose(
            math.fsum(POIDS.values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

        assert COUVERTURE_MIN == 0.60
        assert SEUIL_RISQUE == 40.0

        assert note_valide(0) == 0.0
        assert note_valide(100) == 100.0

        assert note_valide(-1) is None
        assert note_valide(101) is None
        assert note_valide(float("nan")) is None
        assert note_valide(True) is None

        risques = identifier_risques({
            "fiabilite": 30,
            "regularite": 80,
            "resistance": 75,
            "adaptation_conditions": 70,
            "stabilite_performance": 85,
            "potentiel_surprise": 90,
        })

        assert len(risques) == 1
        assert risques[0]["critere"] == "fiabilite"

        assert callable(analyser_course)
        assert callable(analyser_course_m5)

        moteur = MoteurM5()

        assert moteur.nom == MOTEUR
        assert moteur.verifier() is True

        print("X1000 V2.4 — M5")
        print("AUTOTEST : OK")
        print("Moteur : M5")
        print("Spécialité : fiabilité et risques")
        print("Critères indépendants : 6")
        print("Pondérations : 100 %")
        print("Couverture minimale : 60 %")
        print("Seuil de risque : 40 / 100")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Modification archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except Exception as erreur:

        print(
            f"AUTOTEST M5 : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 15. INTERFACE EN LIGNE DE COMMANDE
# ============================================================

def main() -> int:
    """
    Commandes :

    python -m moteurs.m5 --self-test
    python -m moteurs.m5 --input course.json

    L'interface d'analyse est gérée
    par le noyau commun.
    """

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
