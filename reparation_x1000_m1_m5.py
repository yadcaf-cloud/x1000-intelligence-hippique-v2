#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.4 - Préparation isolée des corrections M1 à M5.

Aucun moteur exécuté, aucune collecte, aucun FIGÉ, aucune archive,
aucun commit, push ou publication. Python >= 3.10.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

VERSION = "2.4"
FICHIERS = ("m1.py", "m2.py", "m3.py", "m4.py", "m5.py", "noyau_commun.py")
DESTINATION = "moteurs_corriges_v24"


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def verifier_syntaxe(texte: str, nom: str) -> ast.Module:
    return ast.parse(texte, filename=nom)


def _controle_ordre(arbre: ast.AST) -> bool:
    """Détecte un contrôle de comparaison et une exception dans sa branche.

    Ce contrôle est structurel : il ne prouve pas le comportement à l'exécution.
    """
    for node in ast.walk(arbre):
        if not isinstance(node, ast.If):
            continue
        tests = list(ast.walk(node.test))
        comparaison = any(
            isinstance(x, ast.Compare)
            and isinstance(x.left, ast.Name)
            and x.left.id == "score"
            and len(x.ops) == 1
            and isinstance(x.ops[0], ast.Gt)
            and len(x.comparators) == 1
            and isinstance(x.comparators[0], ast.Name)
            and x.comparators[0].id == "score_precedent"
            for x in tests
        )
        garde = any(
            isinstance(x, ast.Compare)
            and isinstance(x.left, ast.Name)
            and x.left.id == "score_precedent"
            and len(x.ops) == 1
            and isinstance(x.ops[0], ast.IsNot)
            and len(x.comparators) == 1
            and isinstance(x.comparators[0], ast.Constant)
            and x.comparators[0].value is None
            for x in tests
        )
        leve = any(isinstance(x, ast.Raise) for statement in node.body
                   for x in ast.walk(statement))
        if comparaison and garde and leve:
            return True
    return False


def _lignes(texte: str) -> str:
    if "\r" in texte:
        raise RuntimeError("Fin de ligne CR/CRLF non prise en charge sans conversion")
    return texte


def corriger_classement(texte: str, numero: int) -> str:
    if type(numero) is not int or numero not in (1, 2, 3):
        raise ValueError("Correction limitée à M1, M2 et M3")
    nom = f"m{numero}.py"
    texte = _lignes(texte)
    arbre = verifier_syntaxe(texte, nom)
    if "score_precedent" in texte or _controle_ordre(arbre):
        raise RuntimeError(f"M{numero} : protection déjà présente ou structure inconnue")

    # Ancres confirmées sur la branche X1000 V2.4 : deux blocs de classement
    # (classement_complet et classement_partiel), dans une même boucle.
    ancien = "        numeros = set()\n\n        for rang, cheval in enumerate(\n"
    ancre = "            if (\n" + f'                "score_m{numero}" in cheval\n'
    score = "            score = cheval.get(\"score\")\n"
    validation = "            if not score_valide(score):\n"
    if texte.count(ancien) != 1 or texte.count(ancre) != 1:
        raise RuntimeError(f"M{numero} : ancres absentes ou ambiguës")
    if texte.count(score) < 1:
        raise RuntimeError(f"M{numero} : lecture du score introuvable")

    avant, apres = texte.split(ancre, 1)
    # Vérifier que l'ancre est située dans la boucle attendue, après validation.
    pos_boucle = avant.rfind(ancien)
    pos_score = avant.rfind(score)
    pos_validation = avant.rfind(validation)
    if not (0 <= pos_boucle < pos_score < pos_validation):
        raise RuntimeError(f"M{numero} : ordre des validations non confirmé")
    # Vérifier AST : la validation est bien dans une fonction, sans dupliquer
    # l'insertion dans plusieurs contextes.
    if not any(isinstance(x, ast.FunctionDef) for x in ast.walk(arbre)):
        raise RuntimeError(f"M{numero} : aucune fonction détectée")

    controle = (
        "            # Contrôle décroissant après validation du score.\n"
        "            if (\n"
        "                score_precedent is not None\n"
        "                and score > score_precedent\n"
        "            ):\n"
        "                raise RuntimeError(\n"
        f'                    "M{numero} : ordre des scores invalide"\n'
        "                )\n"
        "            score_precedent = score\n\n"
    )
    corrige = texte.replace(
        ancien,
        "        numeros = set()\n        score_precedent = None\n\n"
        "        for rang, cheval in enumerate(\n", 1
    )
    corrige = corrige.replace(ancre, controle + ancre, 1)
    if not _controle_ordre(verifier_syntaxe(corrige, nom)):
        raise RuntimeError(f"M{numero} : contrôle absent après correction")
    if corrige.count("score_precedent = score") != 1:
        raise RuntimeError(f"M{numero} : insertion non unique")
    return corrige


def verifier_moteur_existant(texte: str, numero: int) -> str:
    if type(numero) is not int or numero not in (4, 5):
        raise ValueError("Vérification limitée à M4 et M5")
    arbre = verifier_syntaxe(texte, f"m{numero}.py")
    if not _controle_ordre(arbre):
        raise RuntimeError(f"M{numero} : protection d'ordre non confirmée")
    if "score_precedent = None" not in texte or "score_precedent = score" not in texte:
        raise RuntimeError(f"M{numero} : initialisation/mise à jour absente")
    return texte


def corriger_noyau(texte: str) -> str:
    texte = _lignes(texte)
    verifier_syntaxe(texte, "noyau_commun.py")
    ancien = (
        "        type(identifiant) not in (str, int)\n"
        "        or not str(identifiant).strip()"
    )
    nouveau = (
        "        not isinstance(identifiant, str)\n"
        "        or not identifiant.strip()"
    )
    if texte.count(ancien) != 1:
        raise RuntimeError("Noyau : ancre inconnue ou non unique")
    corrige = texte.replace(ancien, nouveau, 1)
    verifier_syntaxe(corrige, "noyau_commun.py")
    return corrige


def _fichier_regulier(chemin: Path) -> bool:
    return chemin.is_file() and not chemin.is_symlink()


def reparer() -> Path:
    racine = Path(__file__).resolve().parent
    source = racine / "moteurs"
    destination = racine / DESTINATION
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError("Dossier moteurs absent ou lien symbolique")
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Destination déjà présente : écrasement interdit")

    empreintes: dict[str, str] = {}
    corrections: dict[str, str] = {}
    for nom in FICHIERS:
        chemin = source / nom
        if not _fichier_regulier(chemin):
            raise RuntimeError(f"Original absent ou lien symbolique : {nom}")
        avant = sha256(chemin)
        texte = chemin.read_text(encoding="utf-8")
        if sha256(chemin) != avant:
            raise RuntimeError(f"Original changé pendant la lecture : {nom}")
        verifier_syntaxe(texte, nom)
        if nom in ("m1.py", "m2.py", "m3.py"):
            corrige = corriger_classement(texte, int(nom[1]))
        elif nom in ("m4.py", "m5.py"):
            corrige = verifier_moteur_existant(texte, int(nom[1]))
        else:
            corrige = corriger_noyau(texte)
        verifier_syntaxe(corrige, nom)
        empreintes[nom] = avant
        corrections[nom] = corrige

    # Le dossier temporaire reste dans la racine pour un renommage local.
    with tempfile.TemporaryDirectory(prefix=".x1000_v24_", dir=racine) as temp:
        preparation = Path(temp) / DESTINATION
        preparation.mkdir(mode=0o700)
        for nom in FICHIERS:
            chemin = preparation / nom
            chemin.write_text(corrections[nom], encoding="utf-8")
            verifier_syntaxe(chemin.read_text(encoding="utf-8"), nom)
        for nom, empreinte in empreintes.items():
            chemin = source / nom
            if not _fichier_regulier(chemin) or sha256(chemin) != empreinte:
                raise RuntimeError(f"Original modifié : {nom}")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Destination apparue pendant la préparation")
        # mkdir est exclusif : une destination concurrente n'est jamais écrasée.
        try:
            destination.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise RuntimeError("Destination créée par un autre processus") from exc
        try:
            for nom in FICHIERS:
                cible = destination / nom
                # Mode x : interdit l'écrasement d'un fichier préexistant.
                with cible.open("x", encoding="utf-8") as sortie:
                    sortie.write(corrections[nom])
                verifier_syntaxe(cible.read_text(encoding="utf-8"), nom)
            for nom, empreinte in empreintes.items():
                chemin = source / nom
                if not _fichier_regulier(chemin) or sha256(chemin) != empreinte:
                    raise RuntimeError(f"Original modifié en fin de copie : {nom}")
        except Exception:
            # Ne supprimer que nos fichiers attendus, jamais les archives.
            for nom in FICHIERS:
                cible = destination / nom
                if cible.is_file() and not cible.is_symlink():
                    cible.unlink()
            try:
                destination.rmdir()
            except OSError:
                pass
            raise

    print("X1000 V2.4 - Préparation terminée :", destination)
    for nom in FICHIERS:
        print("SYNTAXE OK :", nom)
    print("Originaux, FIGÉS, archives : aucune écriture intentionnelle")
    print("Aucun moteur exécuté ; aucun commit, push ou pronostic publié")
    print("Revue des différences et tests fonctionnels nécessaires")
    return destination


class TestsReparation(unittest.TestCase):
    def test_syntaxe_invalide(self):
        with self.assertRaises(SyntaxError):
            verifier_syntaxe("def x(: pass", "test.py")

    def test_numeros_refuses(self):
        for numero in (0, 4, 5, True, "1"):
            with self.subTest(numero=numero), self.assertRaises(ValueError):
                corriger_classement("pass\n", numero)

    def test_ancres_absentes(self):
        for numero in (1, 2, 3):
            with self.subTest(numero=numero), self.assertRaises(RuntimeError):
                corriger_classement("def x():\n    pass\n", numero)

    def test_noyau_refuse_ambiguite(self):
        with self.assertRaises(RuntimeError):
            corriger_noyau("def x():\n    return True\n")

    def test_noyau_transformation(self):
        original = ("def verifier(identifiant):\n    if (\n"
                    "        type(identifiant) not in (str, int)\n"
                    "        or not str(identifiant).strip()\n"
                    "    ):\n        return False\n    return True\n")
        corrige = corriger_noyau(original)
        self.assertIn("not isinstance(identifiant, str)", corrige)
        self.assertNotIn("type(identifiant) not in", corrige)

    def test_protection_m4_m5(self):
        exemple = ("def verifier(scores):\n    score_precedent = None\n"
                   "    for score in scores:\n"
                   "        if score_precedent is not None and score > score_precedent:\n"
                   "            raise RuntimeError('ordre')\n"
                   "        score_precedent = score\n")
        for numero in (4, 5):
            self.assertEqual(verifier_moteur_existant(exemple, numero), exemple)
        with self.assertRaises(RuntimeError):
            verifier_moteur_existant("def x(): pass\n", 4)

    def test_controle_ordre_negatif(self):
        exemple = "def f(score, score_precedent):\n    if score > score_precedent:\n        pass\n"
        self.assertFalse(_controle_ordre(verifier_syntaxe(exemple, "test.py")))

    def test_pas_execution_lors_analyse(self):
        # ast.parse ne doit pas exécuter l'expression.
        verifier_syntaxe("raise RuntimeError('NE PAS EXECUTER')\n", "test.py")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Tests intégrés sans toucher aux moteurs")
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestsReparation)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    reparer()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, SyntaxError, UnicodeError) as erreur:
        print(f"ERREUR X1000 : {erreur}", file=sys.stderr)
        sys.exit(1)
