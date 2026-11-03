#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.3 - M5 : fiabilite et risques, lecture seule.

Ne collecte ni ne certifie les donnees PMU. Les indicateurs doivent etre
verifies en amont. Aucun FIGE, publication ou ecriture de fichier.
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
VERSION = "2.3"
MIN_PARTANTS = 5
MIN_COUVERTURE = 0.60
SEUIL_RISQUE = 40

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


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_valide(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None

    try:
        note = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(note):
        return None

    return note if 0 <= note <= 100 else None


def verifier_course(course: Any) -> tuple[bool, str]:
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

        if (
            date_depart.tzinfo is None
            or date_depart.utcoffset() is None
        ):
            return False, "Fuseau horaire absent"

        if date_depart <= datetime.now(timezone.utc):
            return False, "Depart deja passe"

    except (ValueError, TypeError, OverflowError):
        return False, "Date de depart invalide"

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
    indicateurs = cheval.get("indicateurs_m5")

    if not isinstance(indicateurs, dict):
        indicateurs = {}

    criteres = {}
    couverture_exacte = 0.0
    total = 0.0

    for critere, poids in POIDS.items():
        note = note_valide(indicateurs.get(critere))

        if note is None:
            continue

        criteres[critere] = note
        couverture_exacte += poids
        total += note * poids

    score = None

    if couverture_exacte + 1e-12 >= MIN_COUVERTURE:
        score = round(total / couverture_exacte, 2)

    risques = [
        {
            "critere": critere,
            "note": note,
            "description": RISQUES[critere],
        }
        for critere, note in criteres.items()
        if note < SEUIL_RISQUE
    ]

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": score,
        "score_m5": score,
        "couverture": round(couverture_exacte, 4),
        "criteres": criteres,
        "criteres_manquants": [
            cle for cle in POIDS if cle not in criteres
        ],
        "risques": risques,
        "admissible": score is not None,
    }


def analyser_course(course: Any) -> dict:
    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "analyse_a": maintenant(),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "classement": [],
        "classement_partiel": [],
        "chevaux_analyses": [],
        "chevaux_evalues": 0,
        "alertes_risques": [],
        "donnees_manquantes": [],
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

    resultat["alertes_risques"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "risques": cheval["risques"],
        }
        for cheval in analyses
        if cheval["risques"]
    ]

    resultat["donnees_manquantes"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "criteres_manquants": cheval["criteres_manquants"],
        }
        for cheval in analyses
        if cheval["criteres_manquants"]
    ]

    admissibles = sorted(
        (
            cheval for cheval in analyses
            if cheval["admissible"]
        ),
        key=lambda cheval: (
            -cheval["score_m5"],
            -cheval["couverture"],
            cheval["numero"],
        ),
    )

    resultat["chevaux_evalues"] = len(admissibles)

    classement = [
        {
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            "score_m5": cheval["score_m5"],
            "couverture": cheval["couverture"],
            "risques": cheval["risques"],
        }
        for position, cheval in enumerate(
            admissibles[:5],
            start=1
        )
    ]

    if len(admissibles) >= 5:
        resultat["classement"] = classement
        resultat["statut"] = "ANALYSE_DISPONIBLE"
        resultat["raison"] = (
            "Classement M5 sur indicateurs fournis. "
            "Prediction non garantie."
        )
    else:
        resultat["classement_partiel"] = classement
        resultat["statut"] = "DONNEES_INSUFFISANTES"
        resultat["raison"] = (
            "Moins de cinq chevaux suffisamment documentes"
        )

    return resultat


def analyser_course_m5(course: Any) -> dict:
    return analyser_course(course)


class MoteurM5:
    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)


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
        with Path(args.input).open(
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
            file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
