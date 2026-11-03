#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 - MOTEUR M2
Analyse autonome des aptitudes hippiques.

M2 est independant de M1.
Aucune donnee PMU fictive.
Aucun resultat officiel invente.
Aucun FIGE retroactif.
Aucune publication automatique.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTEUR = "M2"
VERSION = "2.0"
MIN_PARTANTS = 5
MIN_COUVERTURE = 0.60

CRITERES = {
    "forme": 0.25,
    "distance": 0.25,
    "terrain": 0.15,
    "discipline": 0.20,
    "regularite": 0.15,
}


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool):
        return None

    try:
        resultat = float(valeur)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(resultat):
        return None

    if not 0 <= resultat <= 100:
        return None

    return resultat


def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Course invalide"

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
            return False, "Numero de cheval invalide"

        if numero in numeros:
            return False, "Numero de cheval en double"

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
    aptitudes = cheval.get("aptitudes")

    if not isinstance(aptitudes, dict):
        aptitudes = {}

    total = 0.0
    poids_disponible = 0.0
    criteres_valides = {}

    for critere, poids in CRITERES.items():
        valeur = nombre(aptitudes.get(critere))

        if valeur is None:
            continue

        criteres_valides[critere] = valeur
        total += valeur * poids
        poids_disponible += poids

    couverture = round(poids_disponible, 4)

    score = None

    if couverture >= MIN_COUVERTURE:
        score = round(total / poids_disponible, 2)

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": score,
        "couverture": couverture,
        "criteres": criteres_valides,
        "admissible": score is not None,
    }


def analyser_course(course: dict) -> dict:
    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "analyse_a": maintenant(),
        "course_id": course.get("id"),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "classement": [],
        "chevaux_analyses": [],
        "fige": False,
        "publication": False,
    }

    if not valide:
        return resultat

    analyses = []

    for cheval in course["partants"]:
        if cheval["non_partant"]:
            continue

        analyses.append(analyser_cheval(cheval))

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    resultat["chevaux_analyses"] = analyses

    if len(admissibles) < 5:
        resultat["raison"] = (
            "Moins de cinq chevaux avec "
            "des aptitudes suffisamment documentees"
        )
        return resultat

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score"],
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
            "score_m2": cheval["score"],
            "couverture": cheval["couverture"],
        })

    resultat["statut"] = "ANALYSE_DISPONIBLE"
    resultat["raison"] = (
        "Classement M2 calcule sur les aptitudes "
        "documentees. Prediction non garantie."
    )
    resultat["classement"] = classement

    return resultat


def charger_json(chemin: Path) -> Any:
    with chemin.open("r", encoding="utf-8") as fichier:
        return json.load(fichier)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="X1000 V2 - Analyse M2"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course verifiee"
    )

    args = parser.parse_args()

    try:
        course = charger_json(Path(args.input))
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

    except (OSError, ValueError, TypeError) as erreur:
        print(
            f"Erreur M2 : {erreur}",
            file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())