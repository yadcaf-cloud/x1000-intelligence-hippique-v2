#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 - MOTEUR M4
Intelligence tactique et scenarios de course.

Regles :
- Independance totale de M1, M2, M3 et M5.
- Courses physiquement disputees en France.
- Analyse des partants actifs uniquement.
- Aucune donnee PMU inventee.
- Aucune prediction si donnees insuffisantes.
- Aucun FIGE retroactif.
- Aucune modification de main.
- Aucune publication automatique.

Les indicateurs tactiques doivent provenir
de donnees reelles, documentees et verifiees.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTEUR = "M4"
VERSION = "2.0"

MIN_PARTANTS = 5
MIN_COUVERTURE = 0.65

POIDS = {
    "vitesse_depart": 0.15,
    "positionnement": 0.20,
    "adaptation_rythme": 0.20,
    "endurance": 0.20,
    "aptitude_parcours": 0.15,
    "fiabilite_tactique": 0.10,
}


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_valide(valeur: Any) -> float | None:
    """Accepte uniquement les notes de 0 a 100."""

    if isinstance(valeur, bool):
        return None

    try:
        resultat = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(resultat):
        return None

    if not 0 <= resultat <= 100:
        return None

    return resultat


def verifier_course(course: Any) -> tuple[bool, str]:
    """Verifie les conditions minimales de securite."""

    if not isinstance(course, dict):
        return False, "Format de course invalide"

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
    """Calcule un score tactique independant."""

    indicateurs = cheval.get("indicateurs_m4")

    if not isinstance(indicateurs, dict):
        indicateurs = {}

    total = 0.0
    couverture = 0.0
    details = {}

    for critere, poids in POIDS.items():
        valeur = note_valide(indicateurs.get(critere))

        if valeur is None:
            continue

        details[critere] = valeur
        total += valeur * poids
        couverture += poids

    couverture = round(couverture, 4)

    score = None

    if couverture >= MIN_COUVERTURE:
        score = round(total / couverture, 2)

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score_m4": score,
        "couverture": couverture,
        "criteres": details,
        "admissible": score is not None,
    }


def identifier_risques(analyse: dict) -> list[str]:
    """Signale les fragilites tactiques documentees."""

    risques = []
    criteres = analyse["criteres"]

    seuil = 40

    if (
        "vitesse_depart" in criteres
        and criteres["vitesse_depart"] < seuil
    ):
        risques.append("Depart potentiellement difficile")

    if (
        "endurance" in criteres
        and criteres["endurance"] < seuil
    ):
        risques.append("Endurance insuffisante")

    if (
        "adaptation_rythme" in criteres
        and criteres["adaptation_rythme"] < seuil
    ):
        risques.append("Adaptation au rythme incertaine")

    if (
        "positionnement" in criteres
        and criteres["positionnement"] < seuil
    ):
        risques.append("Positionnement defavorable")

    if (
        "fiabilite_tactique" in criteres
        and criteres["fiabilite_tactique"] < seuil
    ):
        risques.append("Fiabilite tactique faible")

    return risques


def analyser_course(course: Any) -> dict:
    """Produit une decision M4 avant le depart."""

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
        "risques_tactiques": [],
        "fige": False,
        "publication": False,
    }

    if not valide:
        return resultat

    analyses = []

    for cheval in course["partants"]:
        if cheval["non_partant"]:
            continue

        analyse = analyser_cheval(cheval)
        analyse["risques"] = identifier_risques(analyse)

        analyses.append(analyse)

    resultat["chevaux_analyses"] = analyses

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    if len(admissibles) < 5:
        resultat["raison"] = (
            "Moins de cinq chevaux avec des "
            "indicateurs tactiques suffisants"
        )
        return resultat

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score_m4"],
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
            "score_m4": cheval["score_m4"],
            "couverture": cheval["couverture"],
            "risques": cheval["risques"],
        })

    risques_tactiques = []

    for cheval in analyses:
        if cheval["risques"]:
            risques_tactiques.append({
                "numero": cheval["numero"],
                "nom": cheval["nom"],
                "risques": cheval["risques"],
            })

    resultat["classement"] = classement
    resultat["risques_tactiques"] = risques_tactiques
    resultat["statut"] = "ANALYSE_DISPONIBLE"
    resultat["raison"] = (
        "Classement tactique M4 calcule "
        "sur les indicateurs disponibles. "
        "Prediction non garantie."
    )

    return resultat


def main() -> int:
    parser = argparse.ArgumentParser(
        description="X1000 V2 - Moteur tactique M4"
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
            f"Erreur M4 : {erreur}",
            file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
