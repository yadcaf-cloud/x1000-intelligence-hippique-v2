#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M4 : TACTIQUE ET SCENARIOS

Moteur sportif independant M4.

- Courses PMU physiquement disputees en France.
- Depart verifie et non encore passe.
- Analyse des partants actifs uniquement.
- Six criteres tactiques independants.
- Donnees documentees et verifiees en amont.
- Cinq positions predites si possible.
- Classement partiel si donnees insuffisantes.
- Detection des risques tactiques.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune modification des archives.

Execution en lecture seule :
    python -m moteurs.m4 --input course.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION
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
    "vitesse_depart": "Depart potentiellement difficile",
    "positionnement": "Positionnement defavorable",
    "adaptation_rythme": "Adaptation au rythme incertaine",
    "endurance": "Endurance potentiellement insuffisante",
    "aptitude_parcours": "Aptitude au parcours faible",
    "fiabilite_tactique": "Fiabilite tactique faible",
}


# ============================================================
# 2. HORODATAGE
# ============================================================

def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def lire_date(valeur: Any) -> datetime | None:
    if not isinstance(valeur, str) or not valeur.strip():
        return None

    try:
        date = datetime.fromisoformat(
            valeur.strip().replace("Z", "+00:00")
        )

        if date.utcoffset() is None:
            return None

        return date.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


# ============================================================
# 3. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """
    Accepte uniquement les notes numeriques
    comprises entre 0 et 100.
    """

    if type(valeur) not in (int, float):
        return None

    try:
        if not math.isfinite(valeur):
            return None

        if not 0 <= valeur <= 100:
            return None

        return float(valeur)

    except (OverflowError, ValueError):
        return None


# ============================================================
# 4. VALIDATION DE LA CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    if not POIDS:
        raise RuntimeError("Ponderations M4 absentes")

    for critere, poids in POIDS.items():
        if not isinstance(critere, str) or not critere:
            raise RuntimeError("Critere M4 invalide")

        if (
            type(poids) not in (int, float)
            or not math.isfinite(poids)
            or poids <= 0
        ):
            raise RuntimeError("Poids M4 invalide")

    if not math.isclose(
        sum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "La somme des poids M4 doit etre egale a 1"
        )

    if not 0 < COUVERTURE_MIN <= 1:
        raise RuntimeError(
            "Seuil de couverture invalide"
        )


# ============================================================
# 5. VALIDATION SECURISEE DE LA COURSE
# ============================================================

def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Format de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    depart = lire_date(course.get("depart"))

    if depart is None:
        return False, "Date de depart ou fuseau invalide"

    if depart <= datetime.now(timezone.utc):
        return False, "Depart deja passe"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants invalide"

    numeros = set()
    actifs = 0

    for cheval in partants:
        if not isinstance(cheval, dict):
            return False, "Structure de cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        non_partant = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numero de cheval invalide"

        if numero in numeros:
            return False, "Numero de cheval en double"

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom de cheval invalide"

        if type(non_partant) is not bool:
            return False, "Statut non-partant invalide"

        if not non_partant:
            actifs += 1

    if actifs == 0:
        return False, "Aucun partant actif"

    return True, "Course techniquement admissible"


# ============================================================
# 6. ANALYSE INDIVIDUELLE DU CHEVAL
# ============================================================

def analyser_cheval(cheval: dict) -> dict:
    indicateurs = cheval.get(CHAMP)

    if not isinstance(indicateurs, dict):
        indicateurs = {}

    total = 0.0
    couverture = 0.0
    criteres = {}
    manquants = []

    for critere, poids in POIDS.items():
        valeur = note_valide(
            indicateurs.get(critere)
        )

        if valeur is None:
            manquants.append(critere)
            continue

        criteres[critere] = valeur
        total += valeur * poids
        couverture += poids

    couverture = round(couverture, 4)

    score = None

    if couverture + 1e-9 >= COUVERTURE_MIN:
        score = round(
            total / couverture,
            2,
        )

    risques = []

    for critere, libelle in LIBELLES_RISQUES.items():
        valeur = criteres.get(critere)

        if valeur is not None and valeur < SEUIL_RISQUE:
            risques.append(libelle)

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": score,
        "score_m4": score,
        "couverture": couverture,
        "criteres": criteres,
        "criteres_manquants": manquants,
        "admissible": score is not None,
        "risques": risques,
    }


# ============================================================
# 7. ANALYSE SPORTIVE INDEPENDANTE M4
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse tactique independante.

    Aucun classement invente.
    Les chevaux insuffisamment documentes
    restent visibles dans les analyses.
    """

    verifier_configuration()

    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "champ": CHAMP,
        "analyse_a": maintenant(),
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "nombre_partants_actifs": 0,
        "nombre_chevaux_admissibles": 0,
        "classement": [],
        "classement_partiel": [],
        "chevaux_analyses": [],
        "alertes_risques": [],
        "risques_tactiques": [],
        "fige": False,
        "publication": False,
    }

    if not valide:
        return resultat

    actifs = [
        cheval
        for cheval in course["partants"]
        if not cheval["non_partant"]
    ]

    resultat["nombre_partants_actifs"] = len(actifs)

    analyses = [
        analyser_cheval(cheval)
        for cheval in actifs
    ]

    resultat["chevaux_analyses"] = analyses

    risques_tactiques = []

    for analyse in analyses:
        if analyse["risques"]:
            risques_tactiques.append({
                "numero": analyse["numero"],
                "nom": analyse["nom"],
                "risques": list(analyse["risques"]),
            })

    resultat["risques_tactiques"] = risques_tactiques
    resultat["alertes_risques"] = list(
        risques_tactiques
    )

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    resultat["nombre_chevaux_admissibles"] = len(
        admissibles
    )

    if not admissibles:
        resultat["raison"] = (
            "Aucun cheval avec une couverture "
            "tactique suffisante"
        )
        return resultat

    # Classement sportif M4 independant.
    # Departage technique reproductible.
    # Les egalites de score sont signalees.

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score_m4"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    classement = []

    for rang, cheval in enumerate(
        admissibles[:5],
        start=1,
    ):
        egalite = sum(
            autre["score_m4"] == cheval["score_m4"]
            for autre in admissibles
        ) > 1

        classement.append({
            "position_predite": rang,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            "score_m4": cheval["score_m4"],
            "couverture": cheval["couverture"],
            "risques": list(cheval["risques"]),
            "egalite_score": egalite,
        })

    if len(classement) == 5:
        resultat["classement"] = classement
        resultat["statut"] = "ANALYSE_DISPONIBLE"
        resultat["raison"] = (
            "Cinq positions tactiques disponibles. "
            "Prediction non garantie."
        )

    else:
        resultat["classement_partiel"] = classement
        resultat["statut"] = "ANALYSE_PARTIELLE"
        resultat["raison"] = (
            "Classement partiel : moins de "
            "cinq chevaux admissibles"
        )

    return resultat


# ============================================================
# 8. INTERFACE COORDINATEUR X1000
# ============================================================

def analyser_course_m4(course: Any) -> dict:
    return analyser_course(course)


class MoteurM4:
    """
    Moteur tactique independant M4.
    """

    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)


# ============================================================
# 9. SECURITE DU JSON
# ============================================================

def _sans_doublons(
    paires: list[tuple[str, Any]],
) -> dict:
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(
                f"Cle JSON en double : {cle}"
            )

        resultat[cle] = valeur

    return resultat


def _constante_interdite(valeur: str) -> None:
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


# ============================================================
# 10. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    fonction_analyse=analyser_course,
) -> int:
    parser = argparse.ArgumentParser(
        description="X1000 V2.4 - Moteur M4"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course",
    )

    args = parser.parse_args()

    try:
        chemin = Path(args.input)

        with chemin.open(
            "r",
            encoding="utf-8",
        ) as fichier:
            course = json.load(
                fichier,
                object_pairs_hook=_sans_doublons,
                parse_constant=_constante_interdite,
            )

        resultat = fonction_analyse(course)

        print(
            json.dumps(
                resultat,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )

        if resultat["statut"] == "ANALYSE_DISPONIBLE":
            return 0

        if resultat["statut"] in (
            "ANALYSE_PARTIELLE",
            "NON_ANALYSABLE",
        ):
            return 2

        return 1

    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        OverflowError,
    ) as erreur:
        print(
            f"Erreur M4 : {erreur}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    return executer(analyser_course)


# ============================================================
# 11. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
