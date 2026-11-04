#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — VALIDATION CONTROLEE V2.4

Objectifs :
- Verifier les moteurs corriges M1 a M5.
- Verifier le noyau commun.
- Controler la syntaxe des fichiers Python.
- Executer les tests de regression en espace temporaire.
- Eviter l'import accidentel des moteurs originaux.
- Ne pas modifier les fichiers du depot.
- Ne pas declencher de publication ou de FIGE.

Attention :
L'isolation Python n'est pas un bac a sable de securite.
Les tests doivent etre fiables et sans effets de bord.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile

from pathlib import Path


RACINE = Path(__file__).resolve().parent

MOTEURS = RACINE / "moteurs_corriges_v24"
TESTS = RACINE / "test_regression_x1000.py"

FICHIERS_MOTEURS = (
    "m1.py",
    "m2.py",
    "m3.py",
    "m4.py",
    "m5.py",
    "noyau_commun.py",
)

TIMEOUT_SECONDES = 120


def afficher(message: str) -> None:
    print(message, flush=True)


def verifier_fichier(chemin: Path) -> None:
    if chemin.is_symlink():
        raise RuntimeError(
            f"Lien symbolique interdit : {chemin}"
        )

    if not chemin.is_file():
        raise RuntimeError(
            f"Fichier introuvable : {chemin}"
        )


def verifier_syntaxe(chemin: Path) -> None:
    verifier_fichier(chemin)

    try:
        source = chemin.read_text(encoding="utf-8")

        ast.parse(
            source,
            filename=str(chemin),
        )

    except (SyntaxError, UnicodeError) as erreur:
        raise RuntimeError(
            f"Syntaxe invalide : {chemin}\n{erreur}"
        ) from erreur


def verifier_sources() -> None:
    afficher("Verification des sources X1000...")

    if MOTEURS.is_symlink():
        raise RuntimeError(
            "Dossier des moteurs symbolique interdit"
        )

    if not MOTEURS.is_dir():
        raise RuntimeError(
            "Dossier moteurs_corriges_v24 introuvable"
        )

    verifier_syntaxe(TESTS)

    for nom in FICHIERS_MOTEURS:
        chemin = MOTEURS / nom

        verifier_syntaxe(chemin)

        afficher(f"Syntaxe valide : {nom}")

    initialisation = MOTEURS / "__init__.py"

    if initialisation.exists() or initialisation.is_symlink():
        verifier_syntaxe(initialisation)

    # Refuser les liens symboliques dans le paquet copie.
    for chemin in MOTEURS.rglob("*"):
        if chemin.is_symlink():
            raise RuntimeError(
                f"Lien symbolique interdit : {chemin}"
            )

    afficher("Verification syntaxique terminee.")


def creer_environnement(espace: Path) -> Path:
    paquet = espace / "moteurs"

    shutil.copytree(
        MOTEURS,
        paquet,
        symlinks=False,
    )

    # Paquet Python explicite si absent.
    initialisation = paquet / "__init__.py"

    if not initialisation.exists():
        initialisation.write_text(
            "# Paquet temporaire X1000\n",
            encoding="utf-8",
        )

    test_local = espace / TESTS.name

    shutil.copy2(
        TESTS,
        test_local,
    )

    return test_local


def executer_tests(
    espace: Path,
    test_local: Path,
) -> None:
    afficher("Execution des tests de regression...")

    # -I : mode Python isole.
    # -B : pas de creation de fichiers pyc.
    # Le chemin temporaire est ajoute explicitement.
    bootstrap = """
import runpy
import sys

espace = sys.argv[1]
test = sys.argv[2]

sys.path.insert(0, espace)

for nom in list(sys.modules):
    if nom == "moteurs" or nom.startswith("moteurs."):
        del sys.modules[nom]

runpy.run_path(test, run_name="__main__")
"""

    environnement = os.environ.copy()

    # Eviter les personnalisations Python heritees.
    for variable in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
    ):
        environnement.pop(variable, None)

    environnement["PYTHONDONTWRITEBYTECODE"] = "1"
    environnement["PYTHONNOUSERSITE"] = "1"
    environnement["PYTHONUNBUFFERED"] = "1"

    commande = [
        sys.executable,
        "-I",
        "-B",
        "-c",
        bootstrap,
        str(espace),
        str(test_local),
    ]

    try:
        resultat = subprocess.run(
            commande,
            cwd=str(espace),
            env=environnement,
            check=False,
            timeout=TIMEOUT_SECONDES,
        )

    except subprocess.TimeoutExpired as erreur:
        raise RuntimeError(
            "Delai depasse pendant les tests "
            f"({TIMEOUT_SECONDES} secondes)"
        ) from erreur

    if resultat.returncode != 0:
        raise RuntimeError(
            "ECHEC : tests de regression non valides "
            f"(code {resultat.returncode})"
        )


def main() -> int:
    afficher("=" * 55)
    afficher("X1000 PHOENIX - VALIDATION CONTROLEE V2.4")
    afficher("=" * 55)

    try:
        verifier_sources()

        with tempfile.TemporaryDirectory(
            prefix="x1000_validation_"
        ) as dossier:

            espace = Path(dossier).resolve()

            test_local = creer_environnement(
                espace
            )

            executer_tests(
                espace,
                test_local,
            )

    except (OSError, RuntimeError) as erreur:
        afficher("")
        afficher(f"ECHEC : {erreur}")
        afficher("Validation non accordee.")
        return 1

    afficher("")
    afficher("=" * 55)
    afficher("TESTS DE REGRESSION V2.4 : REUSSIS")
    afficher("Moteurs originaux : non modifies")
    afficher("Depot GitHub : non modifie")
    afficher("Publication automatique : aucune")
    afficher("FIGE automatique : aucun")
    afficher("Validation V2.5 : encore necessaire")
    afficher("=" * 55)

    return 0


if __name__ == "__main__":
    sys.exit(main())
