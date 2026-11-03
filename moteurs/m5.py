#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M5 : FIABILITE ET RISQUES

Moteur sportif independant M5.

Mission :
- Etudier chaque cheval actif.
- Evaluer fiabilite, regularite et resistance.
- Analyser adaptation et stabilite.
- Rechercher le potentiel de surprise.
- Identifier les risques documentes.
- Produire cinq positions si possible.
- Conserver les classements partiels.

Securite :
- Courses PMU en France uniquement.
- Localisation et depart verifies en amont.
- Depart obligatoirement futur.
- Aucun non-partant dans les classements.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication ni ecriture d'archives.

Execution :
    python -m moteurs.m5 --input course.json
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

MOTEUR = "M5"
VERSION = "2.4"
CHAMP = "indicateurs_m5"

COUVERTURE_MIN = 0.60
MIN_PARTANTS = 1
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


# ============================================================
# 2. VALIDATION DE LA CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    if not POIDS:
        raise RuntimeError("Ponderations M5 absentes")

    for critere, poids in POIDS.items():
        if not isinstance(critere, str) or not critere:
            raise RuntimeError("Critere M5 invalide")

        if type(poids) not in (int, float):
            raise RuntimeError("Type de poids M5 invalide")

        try:
            poids_float = float(poids)
        except (ValueError, TypeError, OverflowError):
            raise RuntimeError("Poids M5 invalide")

        if not math.isfinite(poids_float) or poids_float <= 0:
            raise RuntimeError("Poids M5 invalide")

    if not math.isclose(
        sum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "La somme des poids M5 doit etre egale a 1"
        )

    if not 0 < COUVERTURE_MIN <= 1:
        raise RuntimeError(
            "Seuil de couverture M5 invalide"
        )


# ============================================================
# 3. HORODATAGE ET DATES
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
# 4. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """
    Accepte uniquement une note numerique
    finie comprise entre 0 et 100.
    """

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
# 5. VALIDATION DE LA COURSE
# ============================================================

def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        type(identifiant) not in (str, int)
        or not str(identifiant).strip()
    ):
        return False, "Identifiant de course invalide"

    if type(identifiant) is int and identifiant <= 0:
        return False, "Identifiant numerique invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    date_depart = lire_date(course.get("depart"))

    if date_depart is None:
        return False, "Date de depart ou fuseau invalide"

    if date_depart <= datetime.now(timezone.utc):
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

    if actifs < MIN_PARTANTS:
        return False, "Aucun partant actif"

    return True, "Course techniquement admissible"


# ============================================================
# 6. ANALYSE INDIVIDUELLE M5
# ============================================================

def analyser_cheval(cheval: dict) -> dict:
    indicateurs = cheval.get(CHAMP)

    if not isinstance(indicateurs, dict):
        indicateurs = {}

    criteres = {}
    manquants = []
    total = 0.0
    couverture_exacte = 0.0

    for critere, poids in POIDS.items():
        note = note_valide(indicateurs.get(critere))

        if note is None:
            manquants.append(critere)
            continue

        criteres[critere] = note
        couverture_exacte += poids
        total += note * poids

    score = None

    if couverture_exacte + 1e-9 >= COUVERTURE_MIN:
        score = round(total / couverture_exacte, 2)

    risques = []

    for critere, note in criteres.items():
        if note < SEUIL_RISQUE:
            risques.append({
                "critere": critere,
                "note": note,
                "description": RISQUES[critere],
            })

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": score,
        "score_m5": score,
        "couverture": round(couverture_exacte, 4),
        "criteres": criteres,
        "criteres_manquants": manquants,
        "risques": risques,
        "admissible": score is not None,
    }


# ============================================================
# 7. ANALYSE SPORTIVE INDEPENDANTE
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Decision sportive independante de M5.

    Aucun classement invente.
    Aucun indicateur manquant remplace.
    """

    verifier_configuration()

    valide, raison = verifier_course(course)

    resultat = {
        "moteur": MOTEUR,
        "version": VERSION,
        "champ": CHAMP,
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "analyse_a": maintenant(),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "nombre_partants_actifs": 0,
        "nombre_chevaux_admissibles": 0,
        "chevaux_evalues": 0,
        "classement": [],
        "classement_partiel": [],
        "chevaux_analyses": [],
        "alertes_risques": [],
        "donnees_manquantes": [],
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

    resultat["alertes_risques"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "risques": list(cheval["risques"]),
        }
        for cheval in analyses
        if cheval["risques"]
    ]

    resultat["donnees_manquantes"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "criteres_manquants": list(
                cheval["criteres_manquants"]
            ),
        }
        for cheval in analyses
        if cheval["criteres_manquants"]
    ]

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    resultat["nombre_chevaux_admissibles"] = len(admissibles)
    resultat["chevaux_evalues"] = len(admissibles)

    if not admissibles:
        resultat["raison"] = (
            "Aucun cheval suffisamment documente "
            "pour une decision M5"
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
        admissibles[:5],
        start=1,
    ):
        egalite = sum(
            autre["score_m5"] == cheval["score_m5"]
            for autre in admissibles
        ) > 1

        classement.append({
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            "score_m5": cheval["score_m5"],
            "couverture": cheval["couverture"],
            "risques": list(cheval["risques"]),
            "egalite_score": egalite,
        })

    if len(classement) == 5:
        resultat["classement"] = classement
        resultat["statut"] = "ANALYSE_DISPONIBLE"
        resultat["raison"] = (
            "Cinq positions M5 disponibles. "
            "Prediction sportive non garantie."
        )

    else:
        resultat["classement_partiel"] = classement
        resultat["statut"] = "ANALYSE_PARTIELLE"
        resultat["raison"] = (
            "Classement partiel conserve : "
            "moins de cinq chevaux admissibles"
        )

    return resultat


# ============================================================
# 8. INTERFACE COORDINATEUR X1000
# ============================================================

def analyser_course_m5(course: Any) -> dict:
    return analyser_course(course)


class MoteurM5:
    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)


# ============================================================
# 9. SECURITE DES FICHIERS JSON
# ============================================================

def _sans_doublons(
    paires: list[tuple[str, Any]],
) -> dict:
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(f"Cle JSON en double : {cle}")

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
        description="X1000 V2.4 - Moteur M5"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course verifiee",
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
            f"Erreur M5 : {erreur}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    return executer(analyser_course)


if __name__ == "__main__":
    sys.exit(main())
