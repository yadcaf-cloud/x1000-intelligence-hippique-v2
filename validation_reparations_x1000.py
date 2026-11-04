#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""X1000 PHOENIX — Validation des moteurs corrigés."""

from pathlib import Path
import os
import subprocess
import sys

RACINE = Path(__file__).resolve().parent
MOTEURS = RACINE / "moteurs_corriges_v24"
TESTS = RACINE / "test_regression_x1000.py"


def main():
    if not MOTEURS.is_dir():
        raise SystemExit(
            "ERREUR : moteurs_corriges_v24 introuvable"
        )

    if not TESTS.is_file():
        raise SystemExit(
            "ERREUR : test_regression_x1000.py introuvable"
        )

    for nom in ("m1", "m2", "m3", "m4", "m5", "noyau_commun"):
        if not (MOTEURS / f"{nom}.py").is_file():
            raise SystemExit(
                f"ERREUR : fichier {nom}.py absent"
            )

    # Créer un espace temporaire indépendant pour
    # empêcher l'import des moteurs originaux.
    import tempfile
    import shutil

    with tempfile.TemporaryDirectory(
        prefix="x1000_validation_"
    ) as dossier:
        espace = Path(dossier)
        paquet = espace / "moteurs"

        shutil.copytree(MOTEURS, paquet)

        test_local = espace / TESTS.name
        shutil.copy2(TESTS, test_local)

        environnement = os.environ.copy()
        environnement["PYTHONDONTWRITEBYTECODE"] = "1"
        environnement["PYTHONPATH"] = str(espace)

        resultat = subprocess.run(
            [sys.executable, "-B", str(test_local)],
            cwd=espace,
            env=environnement,
            check=False,
        )

    if resultat.returncode != 0:
        raise SystemExit(
            "ECHEC : tests de regression non valides"
        )

    print("Tests V2.4 : REUSSIS")
    print("Moteurs originaux : non modifies")
    print("Aucun FIGE ni archive ecrit par ce script")
    print("Validation V2.5 : encore necessaire")


if __name__ == "__main__":
    main()
