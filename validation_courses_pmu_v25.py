#!/usr/bin/env python3
"""X1000 V2.5 : validation structurelle locale, sans collecte ni publication."""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
UTC = dt.timezone.utc

ID_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-R([1-9]\d*)-C([1-9]\d*)$"
)

FORMULES = {
    "Simple gagnant",
    "Simple placé",
    "Couplé gagnant",
    "Couplé placé",
    "2sur4",
    "Trio",
    "Multi",
    "Tiercé",
    "Quarté+",
    "Quinté+",
    "Pick5",
    "Super4",
}


def iso_date(value):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    ):
        return None

    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def aware_datetime(value):
    if not isinstance(value, str):
        return None

    try:
        parsed = dt.datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if (
            parsed.tzinfo is not None
            and parsed.utcoffset() is not None
        ):
            return parsed

        return None

    except (ValueError, OverflowError):
        return None


def validate_course(course, index):
    errors = []
    warnings = []

    if not isinstance(course, dict):
        return {
            "index": index,
            "id": None,
            "valide": False,
            "erreurs": [
                "Course JSON invalide : objet attendu."
            ],
            "avertissements": [],
        }

    cid = course.get("id")

    match = (
        ID_PATTERN.fullmatch(cid)
        if isinstance(cid, str)
        else None
    )

    if match is None or iso_date(match.group(1)) is None:
        errors.append(
            "Identifiant invalide (YYYY-MM-DD-Rn-Cn)."
        )

    date = iso_date(course.get("date"))

    if date is None:
        errors.append("Date invalide (YYYY-MM-DD).")

    if (
        match
        and date
        and match.group(1) != date.isoformat()
    ):
        errors.append(
            "Date et identifiant différents."
        )

    pays = course.get("pays")

    if (
        not isinstance(pays, str)
        or pays.strip().casefold() not in {"france", "fr"}
    ):
        errors.append(
            "Pays France non confirmé."
        )

    hippodrome = course.get("hippodrome")

    if (
        not isinstance(hippodrome, str)
        or not hippodrome.strip()
    ):
        errors.append(
            "Hippodrome manquant."
        )

    depart = aware_datetime(
        course.get("depart")
    )

    if depart is None:
        errors.append(
            "Départ ISO avec fuseau requis."
        )

    elif (
        date
        and depart.astimezone(PARIS).date() != date
    ):
        errors.append(
            "Date du départ incohérente en heure de Paris."
        )

    partants = course.get("partants")
    numeros = []

    if (
        not isinstance(partants, list)
        or not partants
    ):
        errors.append("Partants absents.")

    else:
        for i, partant in enumerate(partants, 1):
            numero = (
                partant.get("numero")
                if isinstance(partant, dict)
                else None
            )

            if type(numero) is not int or numero < 1:
                errors.append(
                    f"Partant {i} : numéro invalide."
                )
            else:
                numeros.append(numero)

            nom = (
                partant.get("nom")
                if isinstance(partant, dict)
                else None
            )

            if (
                not isinstance(nom, str)
                or not nom.strip()
            ):
                errors.append(
                    f"Partant {i} : nom manquant."
                )

        if len(numeros) != len(set(numeros)):
            errors.append(
                "Numéros de partants en doublon."
            )

    formules = course.get("formules")

    if (
        not isinstance(formules, list)
        or not formules
    ):
        errors.append("Formules absentes.")

    else:
        for formule in formules:
            if (
                not isinstance(formule, str)
                or formule not in FORMULES
            ):
                errors.append(
                    f"Formule inconnue : {formule!r}."
                )

        if len(formules) != len(
            set(str(f) for f in formules)
        ):
            errors.append(
                "Formules en doublon."
            )

    source = course.get("source")

    if (
        not isinstance(source, str)
        or not source.strip()
    ):
        errors.append(
            "Source déclarative manquante."
        )

    else:
        warnings.append(
            "Source déclarée, non vérifiée indépendamment."
        )

    verification = course.get(
        "source_verifiee_a"
    )

    if verification is not None:
        instant = aware_datetime(verification)

        if instant is None:
            errors.append(
                "Horodatage de vérification invalide."
            )

        elif instant.astimezone(UTC) > dt.datetime.now(UTC):
            errors.append(
                "Vérification datée dans le futur."
            )

        else:
            warnings.append(
                "Horodatage déclaratif : aucune preuve "
                "de vérification officielle."
            )

    return {
        "index": index,
        "id": cid,
        "valide": not errors,
        "erreurs": errors,
        "avertissements": warnings,
    }


def validate_document(document):
    if isinstance(document, list):
        courses = document

    elif (
        isinstance(document, dict)
        and isinstance(document.get("courses"), list)
    ):
        courses = document["courses"]

    else:
        raise ValueError(
            "JSON attendu : liste ou objet contenant "
            "une liste 'courses'."
        )

    results = [
        validate_course(course, i)
        for i, course in enumerate(courses, 1)
    ]

    occurrences = {}

    for result in results:
        cid = result["id"]

        if isinstance(cid, str):
            occurrences[cid] = (
                occurrences.get(cid, 0) + 1
            )

    for result in results:
        cid = result["id"]

        if (
            isinstance(cid, str)
            and occurrences[cid] > 1
        ):
            result["erreurs"].append(
                "Identifiant de course en doublon."
            )
            result["valide"] = False

    total = len(results)

    valides = sum(
        result["valide"]
        for result in results
    )

    return {
        "systeme": "X1000 V2.5",
        "mode": "VALIDATION_LOCALE_SANS_PUBLICATION",
        "validation_officielle": False,
        "collecte_automatique": False,
        "publication": False,
        "total": total,
        "valides": valides,
        "invalides": total - valides,
        "statut": (
            "AUCUNE_DONNEE"
            if not total
            else (
                "VALIDE"
                if valides == total
                else "ERREURS_DE_VALIDATION"
            )
        ),
        "resultats": results,
    }


def self_test():
    example = {
        "id": "2026-11-03-R1-C1",
        "date": "2026-11-03",
        "pays": "France",
        "hippodrome": "Hippodrome fictif",
        "depart": "2026-11-03T14:00:00+01:00",
        "partants": [
            {
                "numero": 1,
                "nom": "Cheval fictif",
            }
        ],
        "formules": [
            "Simple gagnant"
        ],
        "source": "Exemple fictif",
    }

    good = validate_document({
        "courses": [example]
    })

    assert good["valides"] == 1

    doubles = validate_document({
        "courses": [example, example]
    })

    assert doubles["invalides"] == 2

    empty = validate_document({
        "courses": []
    })

    assert empty["statut"] == "AUCUNE_DONNEE"

    invalid_object = validate_document({
        "courses": [None]
    })

    assert invalid_object["invalides"] == 1

    assert iso_date("2026-02-30") is None

    assert aware_datetime(
        "2026-11-03T14:00:00"
    ) is None

    bad_date = dict(
        example,
        id="2026-02-30-R1-C1"
    )

    assert validate_document(
        [bad_date]
    )["invalides"] == 1

    bad_partant = dict(
        example,
        partants=[
            {
                "numero": True,
                "nom": "Test"
            }
        ]
    )

    assert validate_document(
        [bad_partant]
    )["invalides"] == 1

    print("SELF-TEST OK : 8 contrôles")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.5 - Validation locale France"
        )
    )

    parser.add_argument(
        "--input",
        default="courses.json"
    )

    parser.add_argument(
        "--output",
        default="rapport_validation.json"
    )

    parser.add_argument(
        "--self-test",
        action="store_true"
    )

    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Autoriser explicitement "
            "l'absence de fichier d'entrée."
        )
    )

    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    path = Path(args.input)

    if not path.is_file():
        print(
            f"DONNEES ABSENTES : {path}. "
            "Aucune course inventée.",
            file=sys.stderr
        )

        return 0 if args.allow_missing else 2

    try:
        document = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        report = validate_document(document)

        output = Path(args.output)

        output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2
            ) + "\n",
            encoding="utf-8"
        )

    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError
    ) as exc:
        print(
            f"ERREUR : {exc}",
            file=sys.stderr
        )

        return 2

    print(
        f"Validation : "
        f"{report['valides']} valides, "
        f"{report['invalides']} invalides, "
        f"{report['total']} courses."
    )

    print(
        f"Statut : {report['statut']} "
        f"| Rapport : {args.output}"
    )

    if report["total"] == 0:
        return 2

    if report["invalides"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
