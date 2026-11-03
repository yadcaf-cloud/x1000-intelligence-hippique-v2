#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 - MOTEUR M5
Analyse autonome des risques et de la fiabilite.

- Independant des moteurs M1, M2, M3, M4.
- Courses PMU physiquement disputees en France.
- Etude de chaque cheval actif.
- Cinq positions predites si donnees suffisantes.
- Aucun participant, pronostic ou resultat invente.
- Aucun FIGE retroactif.
- Aucune publication automatique.
- Aucun fichier existant modifie.

Les indicateurs doivent etre documentes,
verifies et etablis avant le depart.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTEUR = "M5"
VERSION = "2.0"

MIN_PARTANTS = 5
MIN_COUVERTURE = 0.60

# Notes positives : 100 = situation favorable.
POIDS = {
    "fiabilite": 0.25,
    "regularite": 0.20,
    "resistance": 0.15,
    "adaptation_conditions": 0.15,
    "stabilite_performance": 0.15,
    "potentiel_surprise": 0.10,
}

SEUIL_RISQUE = 40


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_valide(valeur: Any) -> float | None:
    """Accepte seulement les notes numeriques 0-100."""

    if isinstance(valeur, bool):
        return None

    if not isinstance(valeur, (int, float)):
        return None

    try:
        valeur = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(valeur):
        return None

    if not 0 <= valeur <= 100:
        return None

    return valeur


def verifier_course(course: Any) -> tuple[bool, str]:
    """Controle les conditions minimales d'analyse."""

    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        isinstance(identifiant, bool)
        or not isinstance(identifiant, (str, int))
        or not str(identifiant).strip()
    ):
        return False, "Identifiant de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    depart = course.get("depart")

    if not isinstance(depart, str):
        return False, "Date de depart absente"

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )
    except ValueError:
        return False, "Date de depart invalide"

    if date_depart.tzinfo is None:
        return False, "Fuseau horaire absent"

    if date_depart <= datetime.now(timezone.utc):
        return False, "Depart deja passe"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants absente"

    numeros = set()
    actifs = 0

    for cheval in partants:
        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        non_partant = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numero invalide"

        if numero in numeros:
            return False, "Numero en double"

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom de cheval invalide"

        if not isinstance(non_partant, bool):
            return False, "Statut non-partant invalide"

        if not non_partant:
            actifs += 1

    if actifs < MIN_PARTANTS:
        return False, "Moins de cinq partants actifs"

    return True, "Course verifiee"


def analyser_cheval(cheval: dict) -> dict:
    """Calcule la fiabilite sportive independante."""

    indicateurs = cheval.get("indicateurs_m5")

    if not isinstance(indicateurs, dict):
        indicateurs = {}

    total = 0.0
    couverture = 0.0
    criteres = {}

    for critere, poids in POIDS.items():
        valeur = note_valide(indicateurs.get(critere))

        if valeur is None:
            continue

        criteres[critere] = valeur
        total += valeur * poids
        couverture += poids

    couverture = round(couverture, 4)

    score = None

    if couverture >= MIN_COUVERTURE:
        score = round(total / couverture, 2)

    risques = []

    noms_risques = {
        "fiabilite": "Fiabilite sportive faible",
        "regularite": "Irregularite des performances",
        "resistance": "Resistance insuffisante",
        "adaptation_conditions": "Adaptation incertaine",
        "stabilite_performance": "Stabilite insuffisante",
        "potentiel_surprise": "Potentiel de surprise faible",
    }

    for critere, valeur in criteres.items():
        if valeur < SEUIL_RISQUE:
            risques.append({
                "critere": critere,
                "note": valeur,
                "description": noms_risques[critere],
            })

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score_m5": score,
        "couverture": couverture,
        "criteres": criteres,
        "risques": risques,
        "admissible": score is not None,
    }


def analyser_course(course: Any) -> dict:
    """Etablit cinq positions M5 avant le depart."""

    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "analyse_a": maintenant(),
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "classement": [],
        "chevaux_analyses": [],
        "alertes_risques": [],
        "fige": False,
        "publication": False,
    }

    if not valide:
        return resultat

    analyses = [
        analyser_cheval(cheval)
        for cheval in course["partants"]
        if not cheval["non_partant"]
    ]

    resultat["chevaux_analyses"] = analyses

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    if len(admissibles) < 5:
        resultat["raison"] = (
            "Moins de cinq chevaux avec des "
            "indicateurs M5 suffisants"
        )
        return resultat

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score_m5"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    classement = []

    for position, cheval in enumerate(
        admissibles[:5], start=1
    ):
        classement.append({
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score_m5": cheval["score_m5"],
            "couverture": cheval["couverture"],
            "risques": cheval["risques"],
        })

    alertes = []

    for cheval in analyses:
        if cheval["risques"]:
            alertes.append({
                "numero": cheval["numero"],
                "nom": cheval["nom"],
                "risques": cheval["risques"],
            })

    resultat["classement"] = classement
    resultat["alertes_risques"] = alertes
    resultat["statut"] = "ANALYSE_DISPONIBLE"
    resultat["raison"] = (
        "Classement independant M5 calcule "
        "sur les indicateurs documentes. "
        "Prediction non garantie."
    )

    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="X1000 V2 - Moteur M5"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course verifiee"
    )

    args = parser.parse_args()

    try:
        chemin = Path(args.input)

        with chemin.open(
            "r",
            encoding="utf-8"
        ) as fichier:
            course = json.load(fichier)

        resultat = analyser_course(course)

        print(json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ))

        if resultat["statut"] == "ANALYSE_DISPONIBLE":
            return 0

        return 2

    except (
        OSError,
        ValueError,
        TypeError,
        OverflowError,
    ) as erreur:
        print(
            f"Erreur M5 : {erreur}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
