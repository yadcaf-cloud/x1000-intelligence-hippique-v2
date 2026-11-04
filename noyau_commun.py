#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""X1000 V2.4 - Noyau commun securise pour M1.

Lecture seule. Aucune collecte, publication,
validation officielle ou modification d'archives.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "2.4"


def note_valide(valeur: Any) -> float | None:
    if isinstance(valeur, bool):
        return None

    if not isinstance(valeur, (int, float)):
        return None

    nombre = float(valeur)

    if not math.isfinite(nombre):
        return None

    if not 0 <= nombre <= 100:
        return None

    return nombre


def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Format de course invalide"

    if not isinstance(course.get("id"), str):
        return False, "Identifiant absent"

    if not course["id"].strip():
        return False, "Identifiant vide"

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
            return False, "Nom de cheval invalide"

        if not isinstance(non_partant, bool):
            return False, "Statut non-partant invalide"

        if not non_partant:
            actifs += 1

    if actifs < 5:
        return False, "Moins de cinq partants actifs"

    return True, "Course structurellement valide"


def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> dict:
    valide, raison = verifier_course(course)

    resultat = {
        "moteur": moteur,
        "version": VERSION,
        "analyse_a": datetime.now(
            timezone.utc
        ).isoformat(),
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "classement": [],
        "chevaux_analyses": [],
        "fige": False,
        "publication": False,
    }

    if not valide:
        return resultat

    if (
        not isinstance(poids, dict)
        or not poids
        or not isinstance(champ, str)
        or not champ
    ):
        resultat["raison"] = "Configuration moteur invalide"
        return resultat

    if (
        isinstance(couverture_min, bool)
        or not isinstance(couverture_min, (int, float))
        or not 0 < couverture_min <= 1
    ):
        resultat["raison"] = "Seuil de couverture invalide"
        return resultat

    if any(
        not isinstance(cle, str)
        or isinstance(valeur, bool)
        or not isinstance(valeur, (int, float))
        or not math.isfinite(valeur)
        or valeur <= 0
        for cle, valeur in poids.items()
    ):
        resultat["raison"] = "Ponderations invalides"
        return resultat

    somme_poids = sum(poids.values())

    if not math.isclose(
        somme_poids, 1.0, abs_tol=1e-9
    ):
        resultat["raison"] = "Somme des poids differente de 1"
        return resultat

    analyses = []

    for cheval in course["partants"]:
        if cheval["non_partant"]:
            continue

        indicateurs = cheval.get(champ)

        if not isinstance(indicateurs, dict):
            indicateurs = {}

        total = 0.0
        couverture = 0.0
        details = {}

        for critere, coefficient in poids.items():
            valeur = note_valide(
                indicateurs.get(critere)
            )

            if valeur is None:
                continue

            total += valeur * coefficient
            couverture += coefficient
            details[critere] = valeur

        couverture = round(couverture, 6)

        score = None

        if couverture >= couverture_min:
            score = round(total / couverture, 2)

        analyses.append({
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": score,
            "couverture": couverture,
            "criteres": details,
            "admissible": score is not None,
        })

    resultat["chevaux_analyses"] = analyses

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    if len(admissibles) < 5:
        resultat["raison"] = (
            "Moins de cinq chevaux suffisamment documentes"
        )
        return resultat

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    resultat["classement"] = [
        {
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score_m1": cheval["score"],
            "couverture": cheval["couverture"],
        }
        for position, cheval in enumerate(
            admissibles[:5], start=1
        )
    ]

    resultat["statut"] = "ANALYSE_DISPONIBLE"
    resultat["raison"] = (
        "Classement calcule sur indicateurs fournis. "
        "Leur provenance doit etre verifiee en amont."
    )

    return resultat


def executer(fonction_analyse) -> int:
    parser = argparse.ArgumentParser(
        description="X1000 - Analyse en lecture seule"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course documentee",
    )

    args = parser.parse_args()

    try:
        with Path(args.input).open(
            "r", encoding="utf-8"
        ) as fichier:
            course = json.load(fichier)

        resultat = fonction_analyse(course)

        print(json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ))

        return (
            0
            if resultat["statut"] == "ANALYSE_DISPONIBLE"
            else 2
        )

    except (OSError, ValueError, TypeError) as erreur:
        print(
            f"Erreur technique : {erreur}",
            file=sys.stderr,
        )
        return 1
