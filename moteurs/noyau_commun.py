#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.4 — noyau technique commun, analyse locale en lecture seule.

Les attestations dans le JSON ne constituent pas une vérification indépendante.
Aucune collecte, publication, écriture d'archive ou création de FIGÉ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION = "2.4"
TAILLE_MAX_OCTETS = 5 * 1024 * 1024
MIN_PARTANTS = 5
SEUIL_RISQUE = 40.0
STATUT_DISPONIBLE = "ANALYSE_DISPONIBLE"
STATUT_INSUFFISANT = "DONNEES_INSUFFISANTES"
STATUT_NON_ANALYSABLE = "NON_ANALYSABLE"
STATUTS_VALIDES = {
    STATUT_DISPONIBLE,
    STATUT_INSUFFISANT,
    STATUT_NON_ANALYSABLE,
}
CHAMPS_MOTEURS = {
    "M1": "statistiques",
    "M2": "decision_sportive",
    "M3": "entourage",
    "M4": "aptitude_parcours",
    "M5": "endurance_potentiel",
}
FORMAT_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
FORMAT_ID = re.compile(
    r"^\d{4}-\d{2}-\d{2}-R[1-9]\d*-C[1-9]\d*$"
)


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


def nombre_fini(valeur: Any) -> float | None:
    if type(valeur) not in (int, float):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None
    return nombre if math.isfinite(nombre) else None


def note_valide(valeur: Any) -> float | None:
    nombre = nombre_fini(valeur)
    return (
        nombre
        if nombre is not None and 0 <= nombre <= 100
        else None
    )


def verifier_configuration(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> float:
    if (
        moteur not in CHAMPS_MOTEURS
        or champ != CHAMPS_MOTEURS[moteur]
    ):
        raise ValueError(
            "Identite ou champ de moteur incompatible"
        )

    if not isinstance(poids, dict) or len(poids) != 5:
        raise ValueError(
            "Cinq ponderations sont requises"
        )

    if nombre_fini(couverture_min) != 1.0:
        raise ValueError(
            "Couverture minimale requise : 1.0"
        )

    coefficients = []

    for critere, valeur in poids.items():
        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise ValueError("Critere invalide")

        coefficient = nombre_fini(valeur)

        if coefficient is None or coefficient <= 0:
            raise ValueError(
                f"Coefficient invalide : {critere}"
            )

        coefficients.append(coefficient)

    total = math.fsum(coefficients)

    if (
        not math.isfinite(total)
        or not math.isclose(
            total, 1.0,
            rel_tol=0,
            abs_tol=1e-12,
        )
    ):
        raise ValueError(
            "La somme des poids doit etre egale a 1"
        )

    return total


def verifier_course(course: Any) -> tuple[bool, str]:
    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        not isinstance(identifiant, str)
        or not FORMAT_ID.fullmatch(identifiant)
    ):
        return False, "Identifiant de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non attestee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non atteste"

    if course.get("partants_confirmes") is not True:
        return False, "Partants non confirmes"

    if course.get("np_confirmes") is not True:
        return False, "Non-partants non confirmes"

    hippodrome = course.get("hippodrome")

    if (
        not isinstance(hippodrome, str)
        or not hippodrome.strip()
    ):
        return False, "Hippodrome manquant"

    depart = course.get("depart")

    if (
        not isinstance(depart, str)
        or not FORMAT_DEPART.fullmatch(depart)
    ):
        return False, "Format ISO du depart invalide"

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )

        if date_depart.utcoffset() is None:
            return False, "Fuseau horaire absent"

        if date_depart <= datetime.now(timezone.utc):
            return False, "Depart deja passe"

        from zoneinfo import ZoneInfo

        date_paris = date_depart.astimezone(
            ZoneInfo("Europe/Paris")
        ).date().isoformat()

        if identifiant[:10] != date_paris:
            return False, "Date de course incoherente"

    except (ValueError, OverflowError):
        return False, "Date de depart invalide"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants absente"

    numeros = set()
    non_partants = set()
    actifs = 0

    for cheval in partants:
        if not isinstance(cheval, dict):
            return False, "Fiche cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        np = cheval.get("non_partant")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros
        ):
            return False, "Numero invalide ou duplique"

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom du cheval invalide"

        if type(np) is not bool:
            return False, "Statut non-partant invalide"

        numeros.add(numero)

        if np:
            non_partants.add(numero)
        else:
            actifs += 1

    if actifs < MIN_PARTANTS:
        return False, "Moins de cinq partants actifs"

    if "nombre_partants" in course:
        if (
            type(course["nombre_partants"]) is not int
            or course["nombre_partants"] != actifs
        ):
            return False, (
                "Nombre de partants actifs incoherent"
            )

    if "non_partants" in course:
        liste = course["non_partants"]

        if (
            not isinstance(liste, list)
            or any(type(n) is not int for n in liste)
            or len(liste) != len(set(liste))
            or set(liste) != non_partants
        ):
            return False, (
                "Liste des non-partants incoherente"
            )

    return True, (
        "Course controlee selon les attestations fournies"
    )


def empreinte_configuration(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> str:
    configuration = {
        "moteur": moteur,
        "poids": poids,
        "champ": champ,
        "couverture_min": couverture_min,
        "noyau": VERSION,
    }

    contenu = json.dumps(
        configuration,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


def analyser_cheval(
    cheval: dict,
    champ: str,
    poids: dict,
    couverture_min: float,
    total_poids: float | None = None,
) -> dict:
    if total_poids is None:
        total_poids = math.fsum(poids.values())

    donnees = cheval.get(champ)

    if donnees is None:
        donnees = {}

    if not isinstance(donnees, dict):
        raise ValueError(
            f"Donnees invalides pour cheval {cheval['numero']}"
        )

    criteres = {}
    coefficients = []
    contributions = []

    for critere, coefficient in poids.items():
        if (
            critere not in donnees
            or donnees[critere] is None
        ):
            continue

        note = note_valide(donnees[critere])

        if note is None:
            raise ValueError(
                f"Note invalide : cheval {cheval['numero']}, "
                f"{critere}"
            )

        poids_normalise = coefficient / total_poids

        criteres[critere] = note
        coefficients.append(poids_normalise)
        contributions.append(note * poids_normalise)

    couverture = min(
        1.0,
        max(0.0, math.fsum(coefficients)),
    )

    admissible = (
        len(criteres) == len(poids)
        and math.isclose(
            couverture, 1.0,
            rel_tol=0,
            abs_tol=1e-9,
        )
    )

    score_brut = (
        math.fsum(contributions) / couverture
        if admissible
        else None
    )

    if (
        score_brut is not None
        and not math.isfinite(score_brut)
    ):
        raise ValueError("Score non fini")

    risques = [
        {
            "critere": k,
            "note": v,
            "motif": "Indicateur faible",
        }
        for k, v in criteres.items()
        if v < SEUIL_RISQUE
    ]

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": (
            round(
                max(0.0, min(100.0, score_brut)),
                2,
            )
            if score_brut is not None
            else None
        ),
        "couverture": round(couverture, 4),
        "criteres": criteres,
        "criteres_manquants": [
            k for k in poids if k not in criteres
        ],
        "risques": risques,
        "admissible": admissible,
        "_score_brut": score_brut,
        "_couverture_brute": couverture,
    }


def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float = 1.0,
) -> dict:
    total_poids = verifier_configuration(
        moteur,
        poids,
        champ,
        couverture_min,
    )

    valide, raison = verifier_course(course)

    resultat = {
        "moteur": moteur,
        "version": VERSION,
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "analyse_a": maintenant(),
        "statut": STATUT_NON_ANALYSABLE,
        "raison": raison,
        "classement": [],
        "classement_partiel": [],
        "chevaux_analyses": [],
        "chevaux_evalues": 0,
        "alertes_risques": [],
        "outsiders_potentiels": [],
        "favoris_a_examiner": [],
        "fige": False,
        "publication": False,
        "configuration_sha256": empreinte_configuration(
            moteur,
            poids,
            champ,
            couverture_min,
        ),
    }

    if not valide:
        return resultat

    analyses = []

    for cheval in course["partants"]:
        if cheval["non_partant"]:
            continue

        analyses.append(
            analyser_cheval(
                cheval,
                champ,
                poids,
                couverture_min,
                total_poids,
            )
        )

    resultat["chevaux_analyses"] = [
        {
            k: v
            for k, v in cheval.items()
            if not k.startswith("_")
        }
        for cheval in analyses
    ]

    resultat["alertes_risques"] = [
        {
            "numero": c["numero"],
            "nom": c["nom"],
            "risques": c["risques"],
        }
        for c in analyses
        if c["risques"]
    ]

    admissibles = sorted(
        (
            c for c in analyses
            if c["admissible"]
        ),
        key=lambda c: (
            -c["_score_brut"],
            -c["_couverture_brute"],
            c["numero"],
        ),
    )

    resultat["chevaux_evalues"] = len(admissibles)

    positions = [
        {
            "position_predite": i,
            "numero": c["numero"],
            "nom": c["nom"],
            "score": c["score"],
            "couverture": c["couverture"],
            "risques": c["risques"],
        }
        for i, c in enumerate(
            admissibles[:5],
            start=1,
        )
    ]

    if len(admissibles) >= 5:
        resultat["classement"] = positions
        resultat["statut"] = STATUT_DISPONIBLE
        resultat["raison"] = (
            "Cinq positions calculees sur indicateurs "
            "fournis ; prediction non garantie"
        )
    else:
        resultat["classement_partiel"] = positions
        resultat["statut"] = STATUT_INSUFFISANT
        resultat["raison"] = (
            "Moins de cinq chevaux admissibles"
        )

    return resultat


def refuser_doublons(paires: list) -> dict:
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(
                f"Cle JSON dupliquee : {cle}"
            )
        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur: str) -> None:
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def charger_json_securise(
    chemin: Path,
) -> tuple[Any, str]:
    if chemin.stat().st_size > TAILLE_MAX_OCTETS:
        raise ValueError(
            "Fichier JSON trop volumineux"
        )

    with chemin.open("rb") as fichier:
        contenu = fichier.read(
            TAILLE_MAX_OCTETS + 1
        )

    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValueError(
            "Fichier JSON trop volumineux"
        )

    course = json.loads(
        contenu.decode("utf-8"),
        object_pairs_hook=refuser_doublons,
        parse_constant=refuser_constante,
    )

    return (
        course,
        hashlib.sha256(contenu).hexdigest(),
    )


def executer(
    analyse: Callable[[Any], dict],
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 - analyse en lecture seule"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course",
    )

    args = parser.parse_args()

    try:
        if not callable(analyse):
            raise ValueError(
                "Analyseur invalide"
            )

        course, empreinte = charger_json_securise(
            Path(args.input)
        )

        resultat = analyse(course)

        if (
            not isinstance(resultat, dict)
            or resultat.get("statut") not in STATUTS_VALIDES
        ):
            raise ValueError(
                "Resultat d'analyse invalide"
            )

        if (
            resultat.get("fige") is not False
            or resultat.get("publication") is not False
        ):
            raise ValueError(
                "FIGE ou publication interdits"
            )

        resultat["source_sha256"] = empreinte

        print(
            json.dumps(
                resultat,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )

        return (
            0
            if resultat["statut"] == STATUT_DISPONIBLE
            else 2
        )

    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        OverflowError,
        KeyError,
        ZeroDivisionError,
    ) as erreur:
        print(
            f"Erreur X1000 : {erreur}",
            file=sys.stderr,
        )
        return 1


def self_test() -> bool:
    assert VERSION == "2.4"
    assert len(CHAMPS_MOTEURS) == 5

    assert note_valide(0) == 0.0
    assert note_valide(100) == 100.0
    assert note_valide(True) is None
    assert note_valide(float("nan")) is None

    poids = {
        "a": 0.2,
        "b": 0.2,
        "c": 0.2,
        "d": 0.2,
        "e": 0.2,
    }

    assert verifier_configuration(
        "M1",
        poids,
        "statistiques",
        1.0,
    ) == 1.0

    resultat = analyser_course(
        {},
        "M1",
        poids,
        "statistiques",
    )

    assert resultat["statut"] == STATUT_NON_ANALYSABLE
    assert resultat["fige"] is False
    assert resultat["publication"] is False

    return True


def main() -> int:
    if sys.argv[1:] == ["--self-test"]:
        try:
            self_test()
            print(
                "X1000 V2.4 - NOYAU COMMUN : SELF-TEST OK"
            )
            return 0
        except Exception as erreur:
            print(
                f"SELF-TEST ECHEC : {erreur}",
                file=sys.stderr,
            )
            return 1

    print(
        "Utiliser python -m moteurs.m1 "
        "--input courses.json (ou M2 a M5)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
