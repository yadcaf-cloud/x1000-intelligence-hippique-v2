#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — AUDIT FINAL

- Tests V2.4
- Contrôles statiques V2.5
- Exécution dans une copie temporaire
- Rapport local
- Aucun commit ni push
- Aucune activation des moteurs
- Aucun accès aux FIGÉS/archives d'origine
"""

from pathlib import Path
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess
import sys
import tempfile


RACINE = Path(__file__).resolve().parent

SCRIPTS = [
    "validation_reparations_x1000.py",
    "controle_securite_x1000_v25.py",
]

FICHIERS = [
    "test_regression_x1000.py",
    "validation_courses_pmu_v25.py",
]


def executer(script, dossier):

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        resultat = subprocess.run(
            [sys.executable, "-B", script],
            cwd=dossier,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        return {
            "script": script,
            "code_retour": resultat.returncode,
            "reussi": resultat.returncode == 0,
            "sortie": resultat.stdout[-12000:],
            "erreurs": resultat.stderr[-12000:],
        }

    except subprocess.TimeoutExpired:
        return {
            "script": script,
            "code_retour": None,
            "reussi": False,
            "erreurs": "Delai depasse",
        }


def main():

    resultats = []

    with tempfile.TemporaryDirectory(
        prefix="x1000_audit_final_"
    ) as temporaire:

        espace = Path(temporaire)

        for nom in SCRIPTS + FICHIERS:
            source = RACINE / nom
            if source.is_file():
                shutil.copy2(source, espace / nom)

        moteurs = RACINE / "moteurs_corriges_v24"

        if not moteurs.is_dir():
            raise SystemExit(
                "Moteurs corriges introuvables"
            )

        shutil.copytree(
            moteurs,
            espace / "moteurs_corriges_v24",
        )

        for script in SCRIPTS:

            if not (espace / script).is_file():
                resultats.append({
                    "script": script,
                    "reussi": False,
                    "erreurs": "Script absent",
                })
                continue

            resultats.append(
                executer(script, espace)
            )

    rapport = {
        "projet": "X1000 PHOENIX",
        "date_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "resultats": resultats,
        "tests_reussis": all(
            r["reussi"] for r in resultats
        ),
        "activation_autorisee": False,
        "publication": False,
        "validation_officielle": False,
    }

    destination = RACINE / "audit_final_x1000.json"

    if destination.exists():
        raise SystemExit(
            "Rapport existant : ecrasement interdit"
        )

    destination.write_text(
        json.dumps(
            rapport,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Rapport cree :", destination)

    for resultat in resultats:
        print(
            resultat["script"],
            "OK" if resultat["reussi"] else "ECHEC"
        )

    print("Activation automatique : INTERDITE")

    return 0 if rapport["tests_reussis"] else 1


if __name__ == "__main__":
    sys.exit(main())
