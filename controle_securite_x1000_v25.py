#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 PHOENIX V2.5 : audit statique local, sans écriture projet.

Python 3.9+. Aucun import ni exécution des modules audités.
Aucune collecte, publication, création de FIGÉ ou modification d'archive.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

RACINE = Path(__file__).resolve().parent
MOTEURS = RACINE / 'moteurs_corriges_v24'
FICHIERS_MOTEURS = ['m1.py', 'm2.py', 'm3.py', 'm4.py', 'm5.py', 'noyau_commun.py']
VALIDATEUR = RACINE / 'validation_courses_pmu_v25.py'
DOSSIERS_PROTEGES = [RACINE / 'figes', RACINE / 'archives',
                     RACINE / 'data' / 'figes', RACINE / 'data' / 'archives']
FICHIERS_PROTEGES = ['figes.json', 'audits.json', 'data/figes.json',
                     'data/audits.json']
MAX_SOURCE = 10 * 1024 * 1024
TAILLE_BLOC = 1024 * 1024


class AuditError(Exception):
    """Erreur de sécurité ou de lecture lors d'un contrôle."""


def _relative(path, root):
    return str(path.relative_to(root)).replace(os.sep, '/')


def _regular_file(path):
    """Refuse les liens symboliques et fichiers non réguliers."""
    if path.is_symlink():
        raise AuditError(f'Lien symbolique interdit : {path}')
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise AuditError(f'Fichier inaccessible : {path} : {exc}') from exc
    if not stat.S_ISREG(mode):
        raise AuditError(f'Fichier non régulier : {path}')


def empreinte(chemin):
    """SHA-256 en lecture par blocs, sans charger tout le fichier."""
    path = Path(chemin)
    _regular_file(path)
    digest = hashlib.sha256()
    try:
        with path.open('rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise AuditError(f'Fichier non régulier ouvert : {path}')
            for block in iter(lambda: handle.read(TAILLE_BLOC), b''):
                digest.update(block)
    except OSError as exc:
        raise AuditError(f'Lecture impossible : {path} : {exc}') from exc
    return digest.hexdigest()


def _scan_directory(folder, root, inventory):
    """Parcours sans suivre les liens symboliques, y compris les dossiers."""
    pending = [folder]
    while pending:
        current = pending.pop()
        if current.is_symlink():
            raise AuditError(f'Dossier symbolique interdit : {current}')
        try:
            if not stat.S_ISDIR(current.lstat().st_mode):
                raise AuditError(f'Dossier non régulier : {current}')
            with os.scandir(current) as entries:
                children = sorted(list(entries), key=lambda e: e.name)
        except OSError as exc:
            raise AuditError(f'Inventaire impossible : {current} : {exc}') from exc
        for entry in children:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    raise AuditError(f'Lien symbolique protégé : {path}')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    inventory[_relative(path, root)] = empreinte(path)
                else:
                    raise AuditError(f'Entrée spéciale protégée : {path}')
            except OSError as exc:
                raise AuditError(f'Entrée inaccessible : {path} : {exc}') from exc


def inventaire_protege(racine=None, dossiers=None, fichiers=None):
    """Empreintes des emplacements connus. L'absence est distinguée du vide."""
    root = Path(racine) if racine is not None else RACINE
    folders = dossiers if dossiers is not None else [root / p.relative_to(RACINE) for p in DOSSIERS_PROTEGES]
    names = fichiers if fichiers is not None else FICHIERS_PROTEGES
    inventory = {}
    for folder in folders:
        folder = Path(folder)
        if folder.is_symlink():
            raise AuditError(f'Dossier symbolique interdit : {folder}')
        if folder.exists():
            _scan_directory(folder, root, inventory)
        else:
            inventory[_relative(folder, root) + '/'] = '<ABSENT>'
    for name in names:
        path = root / name
        if path.is_symlink():
            raise AuditError(f'Lien symbolique protégé : {path}')
        inventory[_relative(path, root)] = empreinte(path) if path.exists() else '<ABSENT>'
    return inventory


def _read_source(path):
    _regular_file(path)
    try:
        with path.open('rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise AuditError(f'Source non régulière : {path}')
            data = handle.read(MAX_SOURCE + 1)
    except OSError as exc:
        raise AuditError(f'Source inaccessible : {path} : {exc}') from exc
    if len(data) > MAX_SOURCE:
        raise AuditError(f'Source trop volumineuse : {path}')
    try:
        return ast.parse(data, filename=str(path))
    except (SyntaxError, ValueError, UnicodeError) as exc:
        raise AuditError(f'Syntaxe ou encodage invalide : {path} : {exc}') from exc


def verifier_syntaxe(chemin):
    """Interface historique conservée : lève une exception en cas d'échec."""
    return _read_source(Path(chemin))


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split('.')[0])
    return result


def _module_names(root):
    names = set()
    for folder in (root, root / 'moteurs_corriges_v24', root / 'moteurs'):
        if folder.is_dir() and not folder.is_symlink():
            try:
                names.update(p.stem for p in folder.iterdir()
                             if p.suffix == '.py' and not p.is_symlink())
            except OSError as exc:
                raise AuditError(f'Liste des modules inaccessible : {exc}') from exc
    return names


def _check_imports(tree, modules, filename):
    """Contrôle indicatif des imports locaux, sans résolution dynamique."""
    issues = []
    for name in sorted(_imports(tree)):
        if name.startswith(('moteur_', 'noyau_', 'validation_')) or name in {'m1', 'm2', 'm3', 'm4', 'm5'}:
            if name not in modules:
                issues.append(f'{filename} : import local potentiellement absent : {name}')
    return issues


def audit(racine=None):
    root = Path(racine) if racine is not None else RACINE
    errors, warnings, checked = [], [], []
    before = after = None
    try:
        before = inventaire_protege(root)
    except (AuditError, OSError, ValueError) as exc:
        errors.append(f'Inventaire initial impossible : {exc}')
    try:
        modules = _module_names(root)
        engine_dir = root / 'moteurs_corriges_v24'
        if engine_dir.is_symlink() or not engine_dir.is_dir():
            errors.append('Dossier moteurs_corriges_v24 absent ou symbolique')
        else:
            for filename in FICHIERS_MOTEURS:
                path = engine_dir / filename
                try:
                    tree = verifier_syntaxe(path)
                    checked.append(str(path.relative_to(root)))
                    warnings.extend(_check_imports(tree, modules, filename))
                except (AuditError, OSError, ValueError) as exc:
                    errors.append(f'{filename} : {exc}')
        validator = root / 'validation_courses_pmu_v25.py'
        try:
            tree = verifier_syntaxe(validator)
            checked.append(str(validator.relative_to(root)))
            defined = {n.name for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for name in ('validate_course', 'validate_document', 'self_test'):
                if name not in defined:
                    warnings.append(f'Interface validateur non détectée : {name}')
        except (AuditError, OSError, ValueError) as exc:
            errors.append(f'Validateur V2.5 : {exc}')
    finally:
        try:
            after = inventaire_protege(root)
        except (AuditError, OSError, ValueError) as exc:
            errors.append(f'Inventaire final impossible : {exc}')
    if before is None or after is None:
        errors.append('Intégrité des fichiers protégés non démontrée')
    elif before != after:
        changed = sorted(k for k in before.keys() | after.keys()
                         if before.get(k) != after.get(k))
        errors.append('Changement détecté dans les emplacements protégés : ' + ', '.join(changed))
    return {'ok': not errors, 'erreurs': errors, 'avertissements': warnings,
            'sources_verifiees': checked,
            'fichiers_proteges': sum(v != '<ABSENT>' for v in (before or {}).values()),
            'integrite_comparee': before is not None and after is not None}


class TestsSecurite(unittest.TestCase):
    def test_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'f'
            p.write_bytes(b'abc')
            self.assertEqual(empreinte(p), hashlib.sha256(b'abc').hexdigest())

    def test_syntaxe_valide_et_invalide(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'x.py'
            p.write_text('def f():\n    return 1\n', encoding='utf-8')
            self.assertIsInstance(verifier_syntaxe(p), ast.AST)
            p.write_text('def f(:\n', encoding='utf-8')
            with self.assertRaises(AuditError):
                verifier_syntaxe(p)

    def test_absence_et_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'figes'
            first = inventaire_protege(root, [folder], [])
            self.assertEqual(first['figes/'], '<ABSENT>')
            folder.mkdir()
            p = folder / 'test.json'
            p.write_bytes(b'a')
            second = inventaire_protege(root, [folder], [])
            self.assertNotEqual(first, second)
            p.write_bytes(b'b')
            self.assertNotEqual(second, inventaire_protege(root, [folder], []))

    def test_lien_symbolique_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'archives'
            folder.mkdir()
            target = root / 'target'
            target.write_bytes(b'secret')
            link = folder / 'link'
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('Liens symboliques indisponibles')
            with self.assertRaises(AuditError):
                inventaire_protege(root, [folder], [])

    def test_imports_statiques(self):
        tree = ast.parse('import noyau_commun\nfrom m2 import analyser\n')
        self.assertEqual(_imports(tree), {'noyau_commun', 'm2'})
        self.assertEqual(_check_imports(tree, {'m2'}, 'm1.py'),
                         ['m1.py : import local potentiellement absent : noyau_commun'])

    def test_source_manquante(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AuditError):
                verifier_syntaxe(Path(tmp) / 'missing.py')

    def test_audit_echec_sans_moteurs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit(Path(tmp))
            self.assertFalse(result['ok'])
            self.assertTrue(result['integrite_comparee'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='X1000 V2.5 - contrôle statique en lecture seule')
    parser.add_argument('--self-test', action='store_true', help='Tests autonomes en dossier temporaire')
    parser.add_argument('--root', type=Path, default=RACINE, help='Racine locale du projet')
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestsSecurite)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 2
    result = audit(args.root)
    print('X1000 PHOENIX - CONTROLE DE SECURITE V2.5')
    for filename in result['sources_verifiees']:
        print('SYNTAXE OK :', filename)
    for warning in result['avertissements']:
        print('AVERTISSEMENT :', warning)
    for error in result['erreurs']:
        print('ERREUR :', error)
    print('Fichiers protégés inventoriés :', result['fichiers_proteges'])
    print('Intégrité comparée :', result['integrite_comparee'])
    print('Compatibilité fonctionnelle M1-M5 : NON PROUVEE (audit statique)')
    print('RESULTAT :', 'CONTROLES STATIQUES REUSSIS' if result['ok'] else 'ECHEC SECURISE')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
