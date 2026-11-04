#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M5 : FIABILITE ET RISQUES

Moteur sportif independant M5.

MISSION :
- Etudier chaque cheval actif.
- Evaluer fiabilite, regularite et resistance.
- Analyser adaptation et stabilite.
- Rechercher le potentiel de surprise.
- Identifier les risques documentes.
- Produire cinq positions si possible.
- Conserver les classements partiels.

SECURITE :
- Courses PMU en France uniquement.
- Validation technique par le noyau commun.
- Depart verifie et obligatoirement futur.
- Aucun non-partant dans les classements.
- Aucune donnee sportive inventee.
- Aucune collecte PMU.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune ecriture d'archives.

EXECUTION :
    python -m moteurs.m5 --input course.json
"""

from __future__ import annotations

import math
import sys
from typing import Any


# ============================================================
# 1. IMPORT DU NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


analyse_commune = noyau_commun.analyser_course
execution_commune = noyau_commun.executer


# ============================================================
# 2. IDENTITE ET CONFIGURATION M5
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
    "fiabilite": "Fiabilite sportive faible",
    "regularite": "Irregularite des performances",
    "resistance": "Resistance insuffisante",
    "adaptation_conditions": "Adaptation incertaine",
    "stabilite_performance": "Stabilite insuffisante",
    "potentiel_surprise": "Potentiel de surprise faible",
}

STATUTS_ATTENDUS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 3. VERIFICATION DE LA CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    """Verifie la compatibilite du moteur M5."""

    version_noyau = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if version_noyau != VERSION:
        raise RuntimeError(
            "Noyau incompatible : "
            f"M5={VERSION}, noyau={version_noyau}"
        )

    if not callable(analyse_commune):
        raise RuntimeError(
            "Analyse commune indisponible"
        )

    if not callable(execution_commune):
        raise RuntimeError(
            "Execution commune indisponible"
        )

    if (
        not isinstance(CHAMP, str)
        or not CHAMP.strip()
    ):
        raise RuntimeError(
            "Champ M5 invalide"
        )

    if not isinstance(POIDS, dict) or not POIDS:
        raise RuntimeError(
            "Ponderations M5 absentes"
        )

    for critere, poids in POIDS.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise RuntimeError(
                "Critere M5 invalide"
            )

        if (
            type(poids) not in (int, float)
            or not math.isfinite(poids)
            or poids <= 0
        ):
            raise RuntimeError(
                f"Poids M5 invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "Somme des poids M5 invalide"
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
            "Criteres de risques M5 incoherents"
        )

    statuts_noyau = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if (
        not isinstance(
            statuts_noyau,
            (set, frozenset, tuple, list),
        )
        or set(statuts_noyau) != STATUTS_ATTENDUS
    ):
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


def verifier_noyau() -> None:
    """Alias de compatibilite."""

    verifier_configuration()


# ============================================================
# 4. VALIDATION DES NOTES
# ============================================================

def note_valide(
    valeur: Any,
) -> float | None:
    """Accepte uniquement une note finie de 0 a 100."""

    if type(valeur) not in (int, float):
        return None

    try:
        note = float(valeur)
    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return None

    if not math.isfinite(note):
        return None

    if not 0 <= note <= 100:
        return None

    return note


# ============================================================
# 5. IDENTIFICATION DES RISQUES M5
# ============================================================

def identifier_risques(
    criteres: dict,
) -> list[dict]:
    """
    Identifie uniquement les risques documentes.

    Les criteres absents ne sont pas transformes
    en risques ou en notes fictives.
    """

    risques_detectes = []

    for critere, description in RISQUES.items():

        note = note_valide(
            criteres.get(critere)
        )

        if (
            note is not None
            and note < SEUIL_RISQUE
        ):
            risques_detectes.append({
                "critere": critere,
                "note": note,
                "description": description,
            })

    return risques_detectes


# ============================================================
# 6. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(
    resultat: Any,
) -> None:
    """Controle la structure et les statuts M5."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat M5 non conforme"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identite M5 incoherente"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statut M5 invalide"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGE interdit dans M5"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans M5"
        )

    for cle in (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    ):

        if not isinstance(
            resultat.get(cle),
            list,
        ):
            raise RuntimeError(
                f"Champ M5 invalide : {cle}"
            )

        for entree in resultat[cle]:

            if not isinstance(entree, dict):
                raise RuntimeError(
                    f"Entree M5 invalide : {cle}"
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
                "Classement partiel M5 incoherent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour "
            "une course non analysable"
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
                "Numero analyse M5 invalide"
            )

        numeros_analyses.add(numero)

        score = analyse.get("score")

        if (
            score is not None
            and note_valide(score) is None
        ):
            raise RuntimeError(
                "Score analyse M5 invalide"
            )

    for cle in (
        "classement",
        "classement_partiel",
    ):

        numeros_classes = set()

        for rang, position in enumerate(
            resultat[cle],
            start=1,
        ):

            numero = position.get("numero")

            if (
                type(numero) is not int
                or numero not in numeros_analyses
                or numero in numeros_classes
            ):
                raise RuntimeError(
                    "Classement M5 incoherent"
                )

            numeros_classes.add(numero)

            if (
                type(position.get("position_predite"))
                is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position predite M5 invalide"
                )

            if note_valide(
                position.get("score")
            ) is None:
                raise RuntimeError(
                    "Score de classement M5 invalide"
                )


# ============================================================
# 7. ENRICHISSEMENT DES ANALYSES M5
# ============================================================

def enrichir_analyses(
    resultat: dict,
) -> None:
    """
    Ajoute les risques et les donnees manquantes.

    Aucun score du noyau n'est modifie.
    """

    alertes = []
    donnees_manquantes = []

    for analyse in resultat["chevaux_analyses"]:

        criteres = analyse.get("criteres")

        if not isinstance(criteres, dict):
            raise RuntimeError(
                "Criteres M5 invalides"
            )

        manquants = [
            critere
            for critere in POIDS
            if note_valide(
                criteres.get(critere)
            ) is None
        ]

        risques = identifier_risques(
            criteres
        )

        analyse["score_m5"] = analyse.get("score")
        analyse["risques"] = risques
        analyse["criteres_manquants"] = manquants
        analyse["admissible"] = (
            analyse.get("score") is not None
        )

        if risques:
            alertes.append({
                "numero": analyse["numero"],
                "nom": analyse["nom"],
                "risques": [
                    dict(risque)
                    for risque in risques
                ],
            })

        if manquants:
            donnees_manquantes.append({
                "numero": analyse["numero"],
                "nom": analyse["nom"],
                "criteres_manquants": list(manquants),
            })

    resultat["alertes_risques"] = alertes
    resultat["donnees_manquantes"] = donnees_manquantes


# ============================================================
# 8. ENRICHISSEMENT DES CLASSEMENTS
# ============================================================

def enrichir_classements(
    resultat: dict,
) -> None:
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

    for cle in (
        "classement",
        "classement_partiel",
    ):

        for position in resultat[cle]:

            numero = position["numero"]
            analyse = analyses[numero]
            score = position["score"]

            egalite = sum(
                autre_score == score
                for autre_score in scores
            ) > 1

            position["score_m5"] = score
            position["risques"] = [
                dict(risque)
                for risque in analyse["risques"]
            ]
            position["egalite_score"] = egalite


# ============================================================
# 9. ANALYSE SPORTIVE INDEPENDANTE M5
# ============================================================

def analyser_course(
    course: Any,
) -> dict:
    """
    Decision sportive autonome M5.

    Le noyau commun valide la course et
    calcule les scores avec les six criteres M5.

    Le moteur enrichit ensuite les resultats
    avec ses risques et ses donnees manquantes.
    """

    verifier_configuration()

    resultat = analyse_commune(
        course=course,
        moteur=MOTEUR,
        poids=POIDS,
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat)

    resultat["alertes_risques"] = []
    resultat["donnees_manquantes"] = []

    if resultat["statut"] == "NON_ANALYSABLE":

        resultat["nombre_partants_actifs"] = 0
        resultat["nombre_chevaux_admissibles"] = 0
        resultat["chevaux_evalues"] = 0

        return resultat

    enrichir_analyses(resultat)
    enrichir_classements(resultat)

    resultat["nombre_partants_actifs"] = len(
        resultat["chevaux_analyses"]
    )

    resultat["nombre_chevaux_admissibles"] = sum(
        analyse.get("score") is not None
        for analyse in resultat["chevaux_analyses"]
    )

    resultat["chevaux_evalues"] = (
        resultat["nombre_chevaux_admissibles"]
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 10. INTERFACE COORDINATEUR X1000
# ============================================================

def analyser_course_m5(
    course: Any,
) -> dict:
    """Point d'entree explicite du moteur M5."""

    return analyser_course(course)


class MoteurM5:
    """
    Moteur M5 independant.

    Exemple :
        moteur = MoteurM5()
        resultat = moteur.analyser(course)
    """

    nom = MOTEUR
    version = VERSION

    def analyser(
        self,
        course: Any,
    ) -> dict:
        return analyser_course(course)


# ============================================================
# 11. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    fonction_analyse=None,
) -> int:
    """Interface compatible avec le noyau commun."""

    verifier_configuration()

    if fonction_analyse is None:
        fonction_analyse = analyser_course

    if not callable(fonction_analyse):
        raise TypeError(
            "Fonction d'analyse M5 invalide"
        )

    return execution_commune(
        fonction_analyse
    )


def main() -> int:
    """
    Execution :
        python -m moteurs.m5 --input course.json

    Codes de sortie :
        0 : analyse disponible
        2 : donnees insuffisantes ou non analysable
        1 : erreur technique
    """

    try:
        return executer(
            analyser_course
        )

    except (
        RuntimeError,
        ValueError,
        TypeError,
        OverflowError,
    ) as erreur:

        print(
            f"Erreur M5 : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 12. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
