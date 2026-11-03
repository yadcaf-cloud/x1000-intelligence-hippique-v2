#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 - MOTEUR M3
Detection des chevaux sous-estimes et
evaluation des favoris vulnerables.

Moteur independant de M1 et M2.
Aucune donnee PMU inventee.
Aucun FIGE automatique.
Aucune publication ni modification des archives.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTEUR = "M3"
VERSION = "2.0"

MIN_PARTANTS = 5
MIN_COUVERTURE = 0.65

POIDS = {
    "forme": 0.25,
    "progression": 0.25,
    "aptitude_parcours": 0.20,
    "regularite": 0.15,
    "potentiel_surprise": 0.15,
}


def horodatage() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_valide(valeur: Any) -> float | None:
    if isinstance(valeur, bool):
        return None

    try:
        nombre = float(valeur)
    except (ValueError, TypeError):
        return None

    if not math.isfinite(nombre):
        return None

    if not 0 <= nombre <= 100:
        return None

    return nombre


def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Format de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    depart = course.get("depart")

    if not isinstance(depart, str):
        return False, "Depart absent"

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )
    except ValueError:
        return False, "Date de depart invalide"

    if date_depart.tzinfo is None:
        return False, "Fuseau horaire absent"

    if date_depart <= datetime.now(timezone.utc):
        return False, "Course deja partie"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Partants absents"

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
            return False, "Nom invalide"

        if not isinstance(non_partant, bool):
            return False, "Statut non-partant invalide"

        if not non_partant:
            actifs += 1

    if actifs < MIN_PARTANTS:
        return False, "Moins de cinq partants actifs"

    return True, "Course verifiee"


def analyser_cheval(cheval: dict) -> dict:
    donnees = cheval.get("indicateurs_m3")

    if not isinstance(donnees, dict):
        donnees = {}

    total = 0.0
    couverture = 0.0
    details = {}

    for critere, poids in POIDS.items():
        valeur = note_valide(donnees.get(critere))

        if valeur is None:
            continue

        total += valeur * poids
        couverture += poids
        details[critere] = valeur

    couverture = round(couverture, 4)

    score = None

    if couverture >= MIN_COUVERTURE:
        score = round(total / couverture, 2)

    cote = cheval.get("cote")

    if isinstance(cote, bool):
        cote = None

    try:
        cote = float(cote)
        if not math.isfinite(cote) or cote <= 1:
            cote = None
    except (ValueError, TypeError):
        cote = None

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score_m3": score,
        "couverture": couverture,
        "cote": cote,
        "criteres": details,
        "admissible": score is not None,
    }


def analyser_course(course: dict) -> dict:
    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "analyse_a": horodatage(),
        "course_id": course.get("id"),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "classement": [],
        "outsiders_potentiels": [],
        "favoris_a_examiner": [],
        "chevaux_analyses": [],
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
        cheval for cheval in analyses
        if cheval["admissible"]
    ]

    if len(admissibles) < 5:
        resultat["raison"] = (
            "Moins de cinq chevaux suffisamment documentes"
        )
        return resultat

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score_m3"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    resultat["classement"] = [
        {
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score_m3": cheval["score_m3"],
            "couverture": cheval["couverture"],
        }
        for position, cheval in enumerate(
            admissibles[:5], start=1
        )
    ]

    # Les seuils ci-dessous sont des regles
    # heuristiques internes, non des garanties.
    for cheval in admissibles:
        cote = cheval["cote"]
        score = cheval["score_m3"]

        if cote is None:
            continue

        if cote >= 10 and score >= 70:
            resultat["outsiders_potentiels"].append({
                "numero": cheval["numero"],
                "nom": cheval["nom"],
                "cote": cote,
                "score_m3": score,
                "motif": (
                    "Cote elevee et indicateurs favorables"
                ),
            })

        if cote <= 4 and score < 55:
            resultat["favoris_a_examiner"].append({
                "numero": cheval["numero"],
                "nom": cheval["nom"],
                "cote": cote,
                "score_m3": score,
                "motif": (
                    "Cote basse et indicateurs insuffisants"
                ),
            })

    resultat["statut"] = "ANALYSE_DISPONIBLE"
    resultat["raison"] = (
        "Classement independant M3 etabli "
        "sur les indicateurs documentes"
    )

    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="X1000 V2 - Moteur M3"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Chemin du fichier JSON de course"
    )

    args = parser.parse_args()

    try:
        chemin = Path(args.input)

        with chemin.open(
            "r", encoding="utf-8"
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

    except (OSError, ValueError, TypeError) as erreur:
        print(
            f"Erreur M3 : {erreur}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
