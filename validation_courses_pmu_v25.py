#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.5 : validation structurelle locale, sans collecte ni FIGE.

Python 3.9+. Interfaces historiques conservees. Aucun moteur n'est execute.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PARIS = ZoneInfo('Europe/Paris')
except ZoneInfoNotFoundError:
    PARIS = None
UTC = dt.timezone.utc

ID_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2})-R([1-9]\d*)-C([1-9]\d*)$', re.ASCII)
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$', re.ASCII)
FORMULES = {
    'Simple gagnant', 'Simple placé', 'Couplé gagnant',
    'Couplé placé', '2sur4', 'Trio', 'Multi', 'Tiercé',
    'Quarté+', 'Quinté+', 'Pick5', 'Super4',
}
MAX_PARTANTS = 100
MAX_COURSES = 10000
MAX_INPUT_BYTES = 20 * 1024 * 1024
PROTECTED_NAMES = {'figes.json', 'audits.json', 'selections.json', 'courses.json'}


def iso_date(value):
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def aware_datetime(value):
    if not isinstance(value, str) or not value or value != value.strip():
        return None
    try:
        normalized = value[:-1] + '+00:00' if value.endswith('Z') else value
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed
    except (ValueError, OverflowError, TypeError):
        return None


def now_utc():
    return dt.datetime.now(UTC)


def in_future(value):
    return value is not None and value.astimezone(UTC) > now_utc()


def paris_datetime(value):
    if value is None or PARIS is None:
        return None
    try:
        return value.astimezone(PARIS)
    except (ValueError, OverflowError):
        return None


def valid_paris_offset(value):
    """Un instant UTC ou un autre fuseau explicite reste admissible.

    Pour un horodatage à décalage explicite, on ne peut pas inférer
    le fuseau géographique original. On contrôle donc la possibilité
    de conversion, et non une fausse preuve d'origine Europe/Paris.
    """
    if value is None or PARIS is None:
        return False
    try:
        converted = value.astimezone(PARIS)
        return converted.utcoffset() is not None
    except (ValueError, OverflowError):
        return False


def non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def valid_number(value):
    return type(value) is int and value > 0


def add_error(errors, message):
    if message not in errors:
        errors.append(message)


def add_warning(warnings, message):
    if message not in warnings:
        warnings.append(message)


def validate_partants(partants, errors, warnings):
    if not isinstance(partants, list) or not partants:
        add_error(errors, 'Partants absents.')
        return
    if len(partants) > MAX_PARTANTS:
        add_error(errors, 'Nombre de partants supérieur à la limite technique autorisée.')
    numeros, noms = [], []
    for index, partant in enumerate(partants, 1):
        if not isinstance(partant, dict):
            add_error(errors, f'Partant {index} : objet JSON attendu.')
            continue
        numero, nom = partant.get('numero'), partant.get('nom')
        if not valid_number(numero):
            add_error(errors, f'Partant {index} : numéro invalide.')
        else:
            numeros.append(numero)
        if not non_empty_string(nom):
            add_error(errors, f'Partant {index} : nom manquant.')
        else:
            noms.append(nom.strip().casefold())
        if 'non_partant' in partant:
            np = partant['non_partant']
            if type(np) is not bool:
                add_error(errors, f'Partant {index} : non_partant doit être booléen.')
            elif np:
                add_warning(warnings, f'Partant {index} : non-partant déclaré, non vérifié officiellement.')
        if 'statut' in partant and not non_empty_string(partant['statut']):
            add_error(errors, f'Partant {index} : statut invalide.')
    if len(numeros) != len(set(numeros)):
        add_error(errors, 'Numéros de partants en doublon.')
    if len(noms) != len(set(noms)):
        add_warning(warnings, 'Noms de partants identiques détectés.')


def validate_formules(formules, errors):
    if not isinstance(formules, list) or not formules:
        add_error(errors, 'Formules absentes.')
        return
    seen = set()
    for formule in formules:
        if not isinstance(formule, str) or formule not in FORMULES:
            add_error(errors, f'Formule inconnue : {formule!r}.')
            continue
        if formule in seen:
            add_error(errors, 'Formules en doublon.')
        seen.add(formule)


def validate_course(course, index):
    """Validation structurelle uniquement, jamais officielle."""
    errors, warnings = [], []
    if not isinstance(course, dict):
        return {
            'index': index, 'id': None, 'valide': False,
            'erreurs': ['Course JSON invalide : objet attendu.'],
            'avertissements': [],
        }
    cid = course.get('id')
    match = ID_PATTERN.fullmatch(cid) if isinstance(cid, str) else None
    if match is None or iso_date(match.group(1)) is None:
        add_error(errors, 'Identifiant invalide (YYYY-MM-DD-Rn-Cn).')
    date = iso_date(course.get('date'))
    if date is None:
        add_error(errors, 'Date invalide (YYYY-MM-DD).')
    if match and date and match.group(1) != date.isoformat():
        add_error(errors, 'Date et identifiant différents.')
    pays = course.get('pays')
    if not isinstance(pays, str) or pays.strip().casefold() not in {'france', 'fr'}:
        add_error(errors, 'Pays France non confirmé.')
    if not non_empty_string(course.get('hippodrome')):
        add_error(errors, 'Hippodrome manquant.')
    if PARIS is None:
        add_error(errors, 'Fuseau Europe/Paris indisponible.')
    depart = aware_datetime(course.get('depart'))
    if depart is None:
        add_error(errors, 'Départ ISO avec fuseau requis.')
    else:
        local = paris_datetime(depart)
        if local is None:
            add_error(errors, 'Conversion du départ en heure de Paris impossible.')
        elif date and local.date() != date:
            add_error(errors, 'Date du départ incohérente en heure de Paris.')
        if not valid_paris_offset(depart):
            add_error(errors, 'Horodatage du départ incohérent.')
    validate_partants(course.get('partants'), errors, warnings)
    validate_formules(course.get('formules'), errors)
    if not non_empty_string(course.get('source')):
        add_error(errors, 'Source déclarative manquante.')
    else:
        add_warning(warnings, 'Source déclarée, non vérifiée indépendamment.')
    verification = course.get('source_verifiee_a')
    if verification is not None:
        instant = aware_datetime(verification)
        if instant is None:
            add_error(errors, 'Horodatage de vérification invalide.')
        elif in_future(instant):
            add_error(errors, 'Vérification datée dans le futur.')
        else:
            add_warning(warnings, 'Horodatage déclaratif : aucune preuve de vérification officielle.')
            if depart is not None:
                if instant > depart:
                    add_warning(warnings, 'Source vérifiée après l’heure de départ déclarée.')
                elif depart - instant > dt.timedelta(minutes=10):
                    add_warning(warnings, 'Vérification antérieure de plus de 10 minutes au départ : fraîcheur insuffisante pour un éventuel FIGE.')
    else:
        add_warning(warnings, 'Aucun horodatage de vérification de source fourni.')
    return {
        'index': index, 'id': cid, 'valide': not errors,
        'erreurs': errors, 'avertissements': warnings,
    }


def validate_document(document):
    if isinstance(document, list):
        courses = document
    elif isinstance(document, dict) and isinstance(document.get('courses'), list):
        courses = document['courses']
    else:
        raise ValueError("JSON attendu : liste ou objet contenant une liste 'courses'.")
    if len(courses) > MAX_COURSES:
        raise ValueError('Nombre de courses supérieur à la limite technique autorisée.')
    results = [validate_course(course, index) for index, course in enumerate(courses, 1)]
    occurrences = Counter(
        result['id'] for result in results if isinstance(result['id'], str)
    )
    for result in results:
        cid = result['id']
        if isinstance(cid, str) and occurrences[cid] > 1:
            add_error(result['erreurs'], 'Identifiant de course en doublon.')
            result['valide'] = False
    total = len(results)
    valides = sum(result['valide'] for result in results)
    invalides = total - valides
    statut = (
        'AUCUNE_DONNEE' if total == 0 else
        'VALIDE' if invalides == 0 else 'ERREURS_DE_VALIDATION'
    )
    return {
        'systeme': 'X1000 V2.5',
        'mode': 'VALIDATION_LOCALE_SANS_PUBLICATION',
        'validation_officielle': False,
        'collecte_automatique': False,
        'publication': False,
        'total': total, 'valides': valides,
        'invalides': invalides, 'statut': statut,
        'resultats': results,
    }


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Clé JSON dupliquée : {key!r}')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'Constante JSON non autorisée : {value}')


def read_document(path):
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError('Entrée symbolique interdite.')
    with path.open('rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('Entrée non régulière.')
        data = handle.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("Fichier d'entrée trop volumineux.")
    return json.loads(
        data.decode('utf-8-sig'),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def write_report(report, output_path, input_path=None):
    """Création atomique exclusive, sans écrasement d'un rapport existant."""
    output = Path(output_path).expanduser().absolute()
    if output.name.casefold() in PROTECTED_NAMES:
        raise ValueError('Destination protégée : écriture interdite.')
    if input_path is not None:
        source = Path(input_path).expanduser().resolve()
        if output.resolve() == source:
            raise ValueError("Le rapport ne peut pas écraser le fichier d'entrée.")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("Dossier de destination invalide.")
    if output.is_symlink() or output.exists():
        raise ValueError('Destination déjà existante ou symbolique interdite.')
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=str(output.parent),
            prefix='.x1000_validation_', suffix='.tmp', delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Exclusif : interdit d'écraser même en cas de concurrence.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def self_test():
    checks = 0

    def check(condition, message):
        nonlocal checks
        if not condition:
            raise AssertionError(message)
        checks += 1

    example = {
        'id': '2026-11-03-R1-C1', 'date': '2026-11-03',
        'pays': 'France', 'hippodrome': 'Hippodrome fictif',
        'depart': '2026-11-03T14:00:00+01:00',
        'partants': [
            {'numero': 1, 'nom': 'Cheval fictif A'},
            {'numero': 2, 'nom': 'Cheval fictif B'},
        ],
        'formules': ['Simple gagnant', 'Simple placé'],
        'source': 'Exemple fictif de test',
    }

    def altered(**changes):
        return dict(example, **changes)

    def invalid(**changes):
        return validate_document([altered(**changes)])['invalides'] == 1

    check(validate_document([example])['valides'] == 1, 'Course valide')
    check(validate_document([example, example])['invalides'] == 2, 'Doublons')
    check(validate_document([])['statut'] == 'AUCUNE_DONNEE', 'Document vide')
    check(validate_document([None])['invalides'] == 1, 'Objet invalide')
    check(iso_date('2026-02-30') is None, 'Date impossible')
    check(iso_date('2026-11-03') is not None, 'Date valide')
    check(aware_datetime('2026-11-03T14:00:00') is None, 'Fuseau obligatoire')
    check(aware_datetime('2026-11-03T13:00:00Z') is not None, 'UTC')
    check(invalid(id='2026-02-30-R1-C1'), 'ID date impossible')
    check(invalid(pays='Belgique'), 'Pays hors France')
    check(invalid(hippodrome=''), 'Hippodrome manquant')
    check(invalid(partants=[{'numero': True, 'nom': 'Test'}]), 'Booléen numéro')
    check(invalid(partants=[
        {'numero': 1, 'nom': 'A'}, {'numero': 1, 'nom': 'B'}
    ]), 'Numéros doublons')
    check(invalid(partants=[]), 'Partants absents')
    check(invalid(formules=['Inconnue']), 'Formule inconnue')
    check(invalid(formules=['Trio', 'Trio']), 'Formules doublons')
    check(invalid(source=''), 'Source manquante')
    check(invalid(source_verifiee_a='2999-01-01T00:00:00Z'), 'Vérification future')
    check(invalid(depart='2026-11-04T14:00:00+01:00'), 'Départ incohérent')
    check(invalid(partants=[
        {'numero': 1, 'nom': 'Test', 'non_partant': 'oui'}
    ]), 'Non-partant invalide')
    check(invalid(date='2026-11-04'), 'Date et ID')
    check(invalid(depart='2026-11-03T14:00:00'), 'Départ sans fuseau')
    check(invalid(formules=[]), 'Formules absentes')
    check(invalid(partants=[None]), 'Partant objet attendu')
    check(invalid(partants=[{'numero': 0, 'nom': 'Test'}]), 'Numéro zéro')
    check(invalid(partants=[{'numero': 1, 'nom': ''}]), 'Nom vide')
    check(invalid(partants=[{'numero': 1, 'nom': 'A', 'statut': ''}]), 'Statut vide')
    check(invalid(source_verifiee_a='invalide'), 'Vérification invalide')
    check(validate_document({'courses': [example]})['valides'] == 1, 'Enveloppe')
    try:
        _unique_pairs([('id', 1), ('id', 2)])
    except ValueError:
        check(True, 'Clé JSON dupliquée')
    else:
        check(False, 'Clé JSON dupliquée')
    print(f'SELF-TEST OK : {checks} contrôles réussis.')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='X1000 V2.5 - Validation locale renforcée des courses françaises'
    )
    parser.add_argument('--input', default='courses.json')
    parser.add_argument('--output', default='rapport_validation.json')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--allow-missing', action='store_true')
    args = parser.parse_args(argv)
    if args.self_test:
        try:
            self_test()
            return 0
        except Exception as exc:
            print(f'SELF-TEST ECHEC : {exc}', file=sys.stderr)
            return 2
    if PARIS is None:
        print('ERREUR : fuseau Europe/Paris indisponible.', file=sys.stderr)
        return 2
    path = Path(args.input).expanduser()
    if not path.is_file():
        print(f'DONNEES ABSENTES : {path}. Aucune course inventée.', file=sys.stderr)
        return 0 if args.allow_missing else 2
    try:
        document = read_document(path)
        report = validate_document(document)
        write_report(report, args.output, input_path=path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f'ERREUR : {exc}', file=sys.stderr)
        return 2
    print(f"Validation : {report['valides']} valides, {report['invalides']} invalides, {report['total']} courses.")
    print(f"Statut : {report['statut']} | Rapport : {args.output}")
    return 2 if report['total'] == 0 else (1 if report['invalides'] else 0)


if __name__ == '__main__':
    sys.exit(main())
