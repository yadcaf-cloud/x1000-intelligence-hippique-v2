#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — NOYAU COMMUN M1 A M5

MISSION
-------
Fournir une interface commune aux cinq moteurs
sportifs independants.

Chaque moteur conserve :
- Son identite.
- Son champ d'analyse.
- Ses cinq criteres.
- Ses propres ponderations.
- Son classement.

SECURITE
--------
- Uniquement courses physiquement dispute es en France.
- Date et depart controles en heure de Paris.
- Aucune note sportive inventee.
- Non-partants exclus.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucun FIGE automatique ou retroactif.
- Aucune modification des archives.
- Aucune validation officielle automatique.

Les notes sont fournies par une source externe
fiable et documentee. Le noyau ne les collecte pas.

INTERFACE
---------
analyser_course(
    course,
    moteur,
    poids,
    champ,
    couverture_min=1.0
)

executer(analyseur)
note_valide(valeur)
"""

from __future__ import annotations

import argparse
import json
import math
import sys

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


VERSION = "2.4"
FUSEAU = ZoneInfo("Europe/Paris")

MOTEURS_VALIDES = frozenset({
    "M1", "M2", "M3", "M4", "M5"
})

STATUTS_VALIDES = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})

CHAMPS_MOTEURS = {
    "M1": "statistiques",
    "M2": "decision_sportive",
    "M3": "entourage",
    "M4": "aptitude_parcours",
    "M5": "endurance_potentiel",
}


# ============================================================
# 1. VALIDATION NUMERIQUE
# ============================================================

def note_valide(valeur: Any) -> bool:
    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 100
    )


def couverture_valide(valeur: Any) -> bool:
    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 1
    )


# ============================================================
# 2. DATE ET HEURE
# ============================================================

def convertir_date(valeur: Any) -> datetime:
    if not isinstance(valeur, str):
        raise ValueError("Date absente ou invalide")

    texte = valeur.strip()

    if not texte:
        raise ValueError("Date vide")

    try:
        date = datetime.fromisoformat(
            texte.replace("Z", "+00:00")
        )
    except ValueError as erreur:
        raise ValueError(
            "Date ISO 8601 invalide"
        ) from erreur

    if date.tzinfo is None:
        raise ValueError(
            "Fuseau horaire obligatoire"
        )

    if date.utcoffset() is None:
        raise ValueError(
            "Fuseau horaire invalide"
        )

    return date.astimezone(FUSEAU)


# ============================================================
# 3. CONFIGURATION MOTEUR
# ============================================================

def verifier_moteur(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> None:

    if moteur not in MOTEURS_VALIDES:
        raise ValueError("Moteur inconnu")

    if CHAMPS_MOTEURS[moteur] != champ:
        raise ValueError(
            "Champ incompatible avec le moteur"
        )

    if not isinstance(poids, dict):
        raise ValueError(
            "Ponderations invalides"
        )

    if len(poids) != 5:
        raise ValueError(
            "Cinq criteres obligatoires"
        )

    for critere, valeur in poids.items():

        if not isinstance(critere, str):
            raise ValueError(
                "Nom de critere invalide"
            )

        if not critere.strip():
            raise ValueError(
                "Critere vide"
            )

        if (
            type(valeur) not in (int, float)
            or not math.isfinite(valeur)
            or valeur <= 0
        ):
            raise ValueError(
                "Ponderation invalide"
            )

    if not math.isclose(
        math.fsum(poids.values()),
        1.0,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "Somme des ponderations invalide"
        )

    if (
        type(couverture_min) not in (int, float)
        or not couverture_valide(couverture_min)
        or couverture_min != 1.0
    ):
        raise ValueError(
            "Couverture minimale invalide"
        )


# ============================================================
# 4. CONTROLE DES COURSES
# ============================================================

def verifier_course(course: Any) -> list:

    if not isinstance(course, dict):
        raise ValueError(
            "Course invalide"
        )

    identifiant = course.get("id")

    if (
        not isinstance(identifiant, str)
        or not identifiant.strip()
    ):
        raise ValueError(
            "Identifiant de course manquant"
        )

    pays = course.get("pays")

    if pays not in ("FR", "France"):
        raise ValueError(
            "Course hors France ou non verifiee"
        )

    if course.get("source_france_confirmee") is not True:
        raise ValueError(
            "Localisation France non confirmee"
        )

    hippodrome = course.get("hippodrome")

    if (
        not isinstance(hippodrome, str)
        or not hippodrome.strip()
    ):
        raise ValueError(
            "Hippodrome manquant"
        )

    depart = convertir_date(
        course.get("depart")
    )

    maintenant = datetime.now(FUSEAU)

    if depart <= maintenant:
        raise ValueError(
            "Depart deja passe"
        )

    if course.get("partants_confirmes") is not True:
        raise ValueError(
            "Partants non confirmes"
        )

    if course.get("np_confirmes") is not True:
        raise ValueError(
            "Non-partants non confirmes"
        )

    chevaux = course.get("chevaux")

    if not isinstance(chevaux, list):
        raise ValueError(
            "Liste des chevaux invalide"
        )

    if len(chevaux) < 5:
        raise ValueError(
            "Moins de cinq chevaux declares"
        )

    numeros = set()
    noms = set()

    for cheval in chevaux:

        if not isinstance(cheval, dict):
            raise ValueError(
                "Fiche cheval invalide"
            )

        numero = cheval.get("numero")
        nom = cheval.get("nom")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros
        ):
            raise ValueError(
                "Numero de cheval invalide"
            )

        if (
            not isinstance(nom, str)
            or not nom.strip()
        ):
            raise ValueError(
                "Nom de cheval invalide"
            )

        nom_normalise = nom.strip().casefold()

        if nom_normalise in noms:
            raise ValueError(
                "Nom de cheval duplique"
            )

        if type(cheval.get("non_partant")) is not bool:
            raise ValueError(
                "Statut non-partant manquant"
            )

        numeros.add(numero)
        noms.add(nom_normalise)

    return chevaux


# ============================================================
# 5. VALIDATION DES NOTES
# ============================================================

def extraire_notes(
    cheval: dict,
    champ: str,
) -> dict:

    evaluations = cheval.get("evaluations")

    if not isinstance(evaluations, dict):
        return {}

    notes = evaluations.get(champ)

    if not isinstance(notes, dict):
        return {}

    return notes


def analyser_cheval(
    cheval: dict,
    poids: dict,
    champ: str,
) -> dict:

    numero = cheval["numero"]
    nom = cheval["nom"]

    resultat = {
        "numero": numero,
        "nom": nom,
        "score": None,
        "couverture": 0.0,
        "admissible": False,
    }

    if cheval["non_partant"]:
        return resultat

    notes = extraire_notes(cheval, champ)

    total = 0.0
    couverture = 0.0

    for critere, coefficient in poids.items():

        note = notes.get(critere)

        if note is None:
            continue

        if not note_valide(note):
            raise ValueError(
                f"Note invalide : {numero}/{critere}"
            )

        total += note * coefficient
        couverture += coefficient

    couverture = min(
        1.0,
        max(0.0, couverture),
    )

    resultat["couverture"] = round(
        couverture, 6
    )

    if math.isclose(
        couverture,
        1.0,
        rel_tol=0,
        abs_tol=1e-9,
    ):
        resultat["score"] = round(
            total, 6
        )
        resultat["admissible"] = True

    return resultat


# ============================================================
# 6. CONSTRUCTION DES CLASSEMENTS
# ============================================================

def construire_classement(
    analyses: list,
    moteur: str,
) -> list:

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score"],
            cheval["numero"],
        )
    )

    classement = []

    for position, cheval in enumerate(
        admissibles[:5],
        start=1,
    ):

        entree = {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "position_predite": position,
            "score": cheval["score"],
            f"score_{moteur.lower()}": cheval["score"],
        }

        classement.append(entree)

    return classement


# ============================================================
# 7. RESULTAT NEUTRE
# ============================================================

def resultat_vide(
    moteur: str,
    statut: str,
    raison: str,
) -> dict:

    return {
        "moteur": moteur,
        "version": VERSION,
        "statut": statut,
        "raison": raison,
        "chevaux_analyses": [],
        "classement": [],
        "classement_partiel": [],
        "fige": False,
        "publication": False,
    }


# ============================================================
# 8. ANALYSE PRINCIPALE
# ============================================================

def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float = 1.0,
) -> dict:

    verifier_moteur(
        moteur,
        poids,
        champ,
        couverture_min,
    )

    try:
        chevaux = verifier_course(course)
    except ValueError as erreur:
        return resultat_vide(
            moteur,
            "NON_ANALYSABLE",
            str(erreur),
        )

    analyses = []

    for cheval in chevaux:
        analyse = analyser_cheval(
            cheval,
            poids,
            champ,
        )
        analyses.append(analyse)

    classement_possible = construire_classement(
        analyses,
        moteur,
    )

    if len(classement_possible) >= 5:
        statut = "ANALYSE_DISPONIBLE"
        classement = classement_possible
        classement_partiel = []
    else:
        statut = "DONNEES_INSUFFISANTES"
        classement = []
        classement_partiel = classement_possible

    return {
        "moteur": moteur,
        "version": VERSION,
        "statut": statut,
        "raison": (
            "Analyse complete"
            if statut == "ANALYSE_DISPONIBLE"
            else "Moins de cinq chevaux admissibles"
        ),
        "course_id": course["id"],
        "champ": champ,
        "chevaux_analyses": analyses,
        "classement": classement,
        "classement_partiel": classement_partiel,
        "fige": False,
        "publication": False,
    }


# ============================================================
# 9. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    analyseur: Callable[[Any], dict],
) -> int:

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 - Analyse locale"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course",
    )

    arguments = parser.parse_args()

    chemin = Path(arguments.input)

    if not chemin.is_file():
        raise ValueError(
            "Fichier d'entree introuvable"
        )

    with chemin.open(
        "r",
        encoding="utf-8",
    ) as fichier:
        course = json.load(fichier)

    resultat = analyseur(course)

    print(
        json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )

    statut = resultat.get("statut")

    if statut == "ANALYSE_DISPONIBLE":
        return 0

    if statut in (
        "DONNEES_INSUFFISANTES",
        "NON_ANALYSABLE",
    ):
        return 2

    return 1


# ============================================================
# 10. AUTOTEST DU NOYAU
# ============================================================

def self_test() -> bool:

    assert VERSION == "2.4"
    assert len(MOTEURS_VALIDES) == 5

    assert note_valide(0)
    assert note_valide(100)
    assert not note_valide(True)
    assert not note_valide(-1)
    assert not note_valide(101)
    assert not note_valide(float("nan"))
    assert not note_valide(float("inf"))

    for moteur in MOTEURS_VALIDES:
        assert moteur in CHAMPS_MOTEURS

    poids_test = {
        "a": 0.20,
        "b": 0.20,
        "c": 0.20,
        "d": 0.20,
        "e": 0.20,
    }

    verifier_moteur(
        "M1",
        poids_test,
        "statistiques",
        1.0,
    )

    invalide = analyser_course(
        course={},
        moteur="M1",
        poids=poids_test,
        champ="statistiques",
        couverture_min=1.0,
    )

    assert invalide["statut"] == "NON_ANALYSABLE"
    assert invalide["classement"] == []
    assert invalide["fige"] is False
    assert invalide["publication"] is False

    return True


# ============================================================
# 11. DEMARRAGE
# ============================================================

def main() -> int:

    try:
        if sys.argv[1:] == ["--self-test"]:
            self_test()

            print("X1000 V2.4 - NOYAU COMMUN")
            print("SELF-TEST : OK")
            print("Moteurs : M1 M2 M3 M4 M5")
            print("Publication : desactivee")
            print("FIGE automatique : desactive")
            print("Archives : inchangees")

            return 0

        print(
            "Utiliser un moteur M1 a M5 "
            "pour analyser une course."
        )
        return 0

    except Exception as erreur:
        print(
            "ERREUR NOYAU : "
            f"{type(erreur).__name__} : {erreur}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
