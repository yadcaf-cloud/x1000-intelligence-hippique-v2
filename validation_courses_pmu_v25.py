#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.5 - VALIDATION RENFORCEE DES COURSES PMU FRANCE

Fonctions :
- Validation structurelle des courses françaises.
- Vérification des identifiants, dates et horaires.
- Contrôle du fuseau Europe/Paris.
- Contrôle des partants et des doublons.
- Validation des formules déclarées.
- Vérification des horodatages déclaratifs.
- Rapport JSON local avec écriture atomique.
- Tests intégrés sans données PMU réelles.

Interdictions :
- Aucune collecte PMU automatique.
- Aucune donnée sportive inventée.
- Aucune validation officielle automatique.
- Aucun FIGE automatique ou rétroactif.
- Aucune publication automatique.
- Aucune modification des archives.

Commandes :
python validation_courses_pmu_v25.py --self-test
python validation_courses_pmu_v25.py --input courses.json
python validation_courses_pmu_v25.py --allow-missing

Compatible Python 3.9+.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile

from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ============================================================
# CONFIGURATION
# ============================================================

try:
    PARIS = ZoneInfo("Europe/Paris")
except ZoneInfoNotFoundError:
    PARIS = None

UTC = dt.timezone.utc

ID_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-R([1-9]\d*)-C([1-9]\d*)$",
    re.ASCII,
)

DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}$",
    re.ASCII,
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

MAX_PARTANTS = 100
MAX_COURSES = 10000
MAX_INPUT_BYTES = 20 * 1024 * 1024

PROTECTED_NAMES = {
    "figes.json",
    "audits.json",
    "selections.json",
    "courses.json",
}

# Ces fichiers sont des données métier ou des archives.
# Le validateur ne doit jamais les écraser.


# ============================================================
# DATES ET HORODATAGES
# ============================================================

def iso_date(value):
    """Convertit une date ISO stricte en objet date."""

    if not isinstance(value, str):
        return None

    if not DATE_PATTERN.fullmatch(value):
        return None

    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def aware_datetime(value):
    """Lit un horodatage ISO disposant d'un fuseau explicite."""

    if not isinstance(value, str):
        return None

    if not value or value != value.strip():
        return None

    try:
        normalized = (
            value[:-1] + "+00:00"
            if value.endswith("Z")
            else value
        )

        parsed = dt.datetime.fromisoformat(normalized)

        if parsed.tzinfo is None:
            return None

        if parsed.utcoffset() is None:
            return None

        return parsed

    except (ValueError, OverflowError, TypeError):
        return None


def now_utc():
    return dt.datetime.now(UTC)


def in_future(value):
    """Détecte un instant postérieur à l'heure actuelle."""

    if value is None:
        return False

    return value.astimezone(UTC) > now_utc()


def paris_datetime(value):
    """Convertit un instant en heure de Paris."""

    if value is None or PARIS is None:
        return None

    return value.astimezone(PARIS)


def valid_paris_offset(value):
    """
    Vérifie le décalage déclaré si l'horodatage
    correspond à une heure locale de Paris.

    Les horaires UTC ou d'autres fuseaux restent
    acceptés car ils représentent un instant absolu.
    """

    if value is None or PARIS is None:
        return False

    try:
        converted = value.astimezone(PARIS)

        return (
            converted.astimezone(UTC)
            == value.astimezone(UTC)
        )

    except (ValueError, OverflowError):
        return False


# ============================================================
# UTILITAIRES
# ============================================================

def non_empty_string(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def valid_number(value):
    return (
        type(value) is int
        and value > 0
    )


def add_error(errors, message):
    if message not in errors:
        errors.append(message)


def add_warning(warnings, message):
    if message not in warnings:
        warnings.append(message)


def validate_partants(partants, errors, warnings):
    """Contrôle les partants sans inventer de statut."""

    if not isinstance(partants, list) or not partants:
        add_error(errors, "Partants absents.")
        return

    if len(partants) > MAX_PARTANTS:
        add_error(
            errors,
            "Nombre de partants supérieur à la limite "
            "technique autorisée."
        )

    numeros = []
    noms = []

    for index, partant in enumerate(partants, 1):

        if not isinstance(partant, dict):
            add_error(
                errors,
                f"Partant {index} : objet JSON attendu."
            )
            continue

        numero = partant.get("numero")
        nom = partant.get("nom")

        if not valid_number(numero):
            add_error(
                errors,
                f"Partant {index} : numéro invalide."
            )
        else:
            numeros.append(numero)

        if not non_empty_string(nom):
            add_error(
                errors,
                f"Partant {index} : nom manquant."
            )
        else:
            noms.append(nom.strip().casefold())

        if "non_partant" in partant:
            np = partant["non_partant"]

            if type(np) is not bool:
                add_error(
                    errors,
                    f"Partant {index} : "
                    "non_partant doit être booléen."
                )

            elif np:
                add_warning(
                    warnings,
                    f"Partant {index} : non-partant déclaré, "
                    "non vérifié officiellement."
                )

        if "statut" in partant:
            statut = partant["statut"]

            if not non_empty_string(statut):
                add_error(
                    errors,
                    f"Partant {index} : statut invalide."
                )

    if len(numeros) != len(set(numeros)):
        add_error(
            errors,
            "Numéros de partants en doublon."
        )

    if len(noms) != len(set(noms)):
        add_warning(
            warnings,
            "Noms de partants identiques détectés."
        )


def validate_formules(formules, errors):
    """Vérifie les formules sans présumer de leur éligibilité."""

    if not isinstance(formules, list) or not formules:
        add_error(errors, "Formules absentes.")
        return

    seen = set()

    for formule in formules:

        if not isinstance(formule, str):
            add_error(
                errors,
                f"Formule inconnue : {formule!r}."
            )
            continue

        if formule not in FORMULES:
            add_error(
                errors,
                f"Formule inconnue : {formule!r}."
            )

        if formule in seen:
            add_error(
                errors,
                "Formules en doublon."
            )

        seen.add(formule)


# ============================================================
# VALIDATION INDIVIDUELLE
# ============================================================

def validate_course(course, index):
    """
    Validation structurelle locale.

    Le résultat 'valide' ne signifie jamais
    qu'une course a été officiellement confirmée.
    """

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

    if match is None:
        add_error(
            errors,
            "Identifiant invalide (YYYY-MM-DD-Rn-Cn)."
        )
    elif iso_date(match.group(1)) is None:
        add_error(
            errors,
            "Identifiant invalide (YYYY-MM-DD-Rn-Cn)."
        )

    date = iso_date(course.get("date"))

    if date is None:
        add_error(
            errors,
            "Date invalide (YYYY-MM-DD)."
        )

    if match and date:
        if match.group(1) != date.isoformat():
            add_error(
                errors,
                "Date et identifiant différents."
            )

    pays = course.get("pays")

    if (
        not isinstance(pays, str)
        or pays.strip().casefold() not in {"france", "fr"}
    ):
        add_error(
            errors,
            "Pays France non confirmé."
        )

    hippodrome = course.get("hippodrome")

    if not non_empty_string(hippodrome):
        add_error(
            errors,
            "Hippodrome manquant."
        )

    if PARIS is None:
        add_error(
            errors,
            "Fuseau Europe/Paris indisponible."
        )

    depart = aware_datetime(course.get("depart"))

    if depart is None:
        add_error(
            errors,
            "Départ ISO avec fuseau requis."
        )

    else:
        local_depart = paris_datetime(depart)

        if local_depart is None:
            add_error(
                errors,
                "Conversion du départ en heure de Paris impossible."
            )

        elif date and local_depart.date() != date:
            add_error(
                errors,
                "Date du départ incohérente en heure de Paris."
            )

        if not valid_paris_offset(depart):
            add_error(
                errors,
                "Horodatage du départ incohérent."
            )

    validate_partants(
        course.get("partants"),
        errors,
        warnings,
    )

    validate_formules(
        course.get("formules"),
        errors,
    )

    source = course.get("source")

    if not non_empty_string(source):
        add_error(
            errors,
            "Source déclarative manquante."
        )
    else:
        add_warning(
            warnings,
            "Source déclarée, non vérifiée indépendamment."
        )

    verification = course.get("source_verifiee_a")

    if verification is not None:

        instant = aware_datetime(verification)

        if instant is None:
            add_error(
                errors,
                "Horodatage de vérification invalide."
            )

        elif in_future(instant):
            add_error(
                errors,
                "Vérification datée dans le futur."
            )

        else:
            add_warning(
                warnings,
                "Horodatage déclaratif : aucune preuve "
                "de vérification officielle."
            )

            if depart is not None:
                if instant > depart:
                    add_warning(
                        warnings,
                        "Source vérifiée après l'heure "
                        "de départ déclarée."
                    )

                elif (
                    depart - instant
                ) > dt.timedelta(minutes=10):
                    add_warning(
                        warnings,
                        "Vérification antérieure de plus "
                        "de 10 minutes au départ : "
                        "fraîcheur insuffisante pour "
                        "un éventuel FIGE."
                    )

    else:
        add_warning(
            warnings,
            "Aucun horodatage de vérification "
            "de source fourni."
        )

    return {
        "index": index,
        "id": cid,
        "valide": not errors,
        "erreurs": errors,
        "avertissements": warnings,
    }


# ============================================================
# VALIDATION DOCUMENT
# ============================================================

def validate_document(document):
    """Valide un ensemble de courses sans écriture."""

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

    if len(courses) > MAX_COURSES:
        raise ValueError(
            "Nombre de courses supérieur à la limite "
            "technique autorisée."
        )

    results = [
        validate_course(course, index)
        for index, course in enumerate(courses, 1)
    ]

    occurrences = Counter(
        result["id"]
        for result in results
        if isinstance(result["id"], str)
    )

    for result in results:

        cid = result["id"]

        if (
            isinstance(cid, str)
            and occurrences[cid] > 1
        ):
            add_error(
                result["erreurs"],
                "Identifiant de course en doublon."
            )

            result["valide"] = False

    total = len(results)

    valides = sum(
        1
        for result in results
        if result["valide"]
    )

    invalides = total - valides

    if total == 0:
        statut = "AUCUNE_DONNEE"

    elif invalides == 0:
        statut = "VALIDE"

    else:
        statut = "ERREURS_DE_VALIDATION"

    return {
        "systeme": "X1000 V2.5",
        "mode": "VALIDATION_LOCALE_SANS_PUBLICATION",
        "validation_officielle": False,
        "collecte_automatique": False,
        "publication": False,
        "total": total,
        "valides": valides,
        "invalides": invalides,
        "statut": statut,
        "resultats": results,
    }


# ============================================================
# ECRITURE SECURISEE DU RAPPORT
# ============================================================

def write_report(report, output_path, input_path=None):
    """
    Ecriture atomique du rapport JSON.

    N'écrase pas les fichiers métier protégés.
    N'écrase pas le fichier d'entrée.
    """

    output = Path(output_path).expanduser().resolve()

    if output.name.casefold() in PROTECTED_NAMES:
        raise ValueError(
            "Destination protégée : écriture interdite."
        )

    if input_path is not None:
        source = Path(input_path).expanduser().resolve()

        if output == source:
            raise ValueError(
                "Le rapport ne peut pas écraser "
                "le fichier d'entrée."
            )

    if not output.parent.is_dir():
        raise ValueError(
            "Le dossier de destination n'existe pas."
        )

    # Refus d'écraser un lien symbolique.
    if output.is_symlink():
        raise ValueError(
            "Destination symbolique interdite."
        )

    content = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(output.parent),
            prefix=".x1000_validation_",
            suffix=".tmp",
            delete=False,
        ) as handle:

            temporary = Path(handle.name)

            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, output)
        temporary = None

    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


# ============================================================
# TESTS INTEGRES
# ============================================================

def self_test():
    """Exécute des contrôles locaux sans réseau."""

    checks = 0

    def check(condition, message):
        nonlocal checks

        if not condition:
            raise AssertionError(message)

        checks += 1

    example = {
        "id": "2026-11-03-R1-C1",
        "date": "2026-11-03",
        "pays": "France",
        "hippodrome": "Hippodrome fictif",
        "depart": "2026-11-03T14:00:00+01:00",
        "partants": [
            {
                "numero": 1,
                "nom": "Cheval fictif A",
            },
            {
                "numero": 2,
                "nom": "Cheval fictif B",
            },
        ],
        "formules": [
            "Simple gagnant",
            "Simple placé",
        ],
        "source": "Exemple fictif de test",
    }

    def altered(**changes):
        return dict(example, **changes)

    check(
        validate_document([example])["valides"] == 1,
        "Course structurellement valide"
    )

    check(
        validate_document([example, example])["invalides"] == 2,
        "Détection des identifiants en doublon"
    )

    check(
        validate_document([])["statut"] == "AUCUNE_DONNEE",
        "Document vide"
    )

    check(
        validate_document([None])["invalides"] == 1,
        "Objet course invalide"
    )

    check(
        iso_date("2026-02-30") is None,
        "Date impossible"
    )

    check(
        iso_date("2026-11-03") is not None,
        "Date ISO valide"
    )

    check(
        aware_datetime("2026-11-03T14:00:00") is None,
        "Fuseau obligatoire"
    )

    check(
        aware_datetime("2026-11-03T13:00:00Z")
        is not None,
        "Horodatage UTC"
    )

    check(
        validate_document([
            altered(id="2026-02-30-R1-C1")
        ])["invalides"] == 1,
        "Identifiant avec date impossible"
    )

    check(
        validate_document([
            altered(pays="Belgique")
        ])["invalides"] == 1,
        "Pays hors France"
    )

    check(
        validate_document([
            altered(hippodrome="")
        ])["invalides"] == 1,
        "Hippodrome manquant"
    )

    check(
        validate_document([
            altered(
                partants=[
                    {"numero": True, "nom": "Test"}
                ]
            )
        ])["invalides"] == 1,
        "Booléen interdit comme numéro"
    )

    check(
        validate_document([
            altered(
                partants=[
                    {"numero": 1, "nom": "A"},
                    {"numero": 1, "nom": "B"},
                ]
            )
        ])["invalides"] == 1,
        "Numéros de partants en doublon"
    )

    check(
        validate_document([
            altered(partants=[])
        ])["invalides"] == 1,
        "Partants absents"
    )

    check(
        validate_document([
            altered(formules=["Formule inconnue"])
        ])["invalides"] == 1,
        "Formule inconnue"
    )

    check(
        validate_document([
            altered(
                formules=[
                    "Trio",
                    "Trio",
                ]
            )
        ])["invalides"] == 1,
        "Formules en doublon"
    )

    check(
        validate_document([
            altered(source="")
        ])["invalides"] == 1,
        "Source manquante"
    )

    check(
        validate_document([
            altered(
                source_verifiee_a="2999-01-01T00:00:00Z"
            )
        ])["invalides"] == 1,
        "Vérification future"
    )

    check(
        validate_document([
            altered(
                depart="2026-11-04T14:00:00+01:00"
            )
        ])["invalides"] == 1,
        "Date de départ incohérente"
    )

    check(
        validate_document([
            altered(
                partants=[
                    {
                        "numero": 1,
                        "nom": "Test",
                        "non_partant": "oui",
                    }
                ]
            )
        ])["invalides"] == 1,
        "Statut non-partant non booléen"
    )

    print(
        f"SELF-TEST OK : {checks} contrôles réussis."
    )

    return True


# ============================================================
# INTERFACE LIGNE DE COMMANDE
# ============================================================

def main(argv=None):

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.5 - Validation locale renforcée "
            "des courses françaises"
        )
    )

    parser.add_argument(
        "--input",
        default="courses.json",
        help="Fichier JSON contenant les courses.",
    )

    parser.add_argument(
        "--output",
        default="rapport_validation.json",
        help="Rapport JSON local.",
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Exécuter les tests intégrés.",
    )

    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Autoriser explicitement l'absence "
            "du fichier d'entrée."
        ),
    )

    args = parser.parse_args(argv)

    if args.self_test:
        try:
            self_test()
            return 0

        except (AssertionError, Exception) as exc:
            print(
                f"SELF-TEST ECHEC : {exc}",
                file=sys.stderr,
            )
            return 2

    if PARIS is None:
        print(
            "ERREUR : fuseau Europe/Paris indisponible.",
            file=sys.stderr,
        )
        return 2

    path = Path(args.input)

    if not path.is_file():
        print(
            f"DONNEES ABSENTES : {path}. "
            "Aucune course inventée.",
            file=sys.stderr,
        )

        return 0 if args.allow_missing else 2

    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError(
                "Fichier d'entrée trop volumineux."
            )

        document = json.loads(
            path.read_text(encoding="utf-8")
        )

        report = validate_document(document)

        write_report(
            report,
            args.output,
            input_path=path,
        )

    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:

        print(
            f"ERREUR : {exc}",
            file=sys.stderr,
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
