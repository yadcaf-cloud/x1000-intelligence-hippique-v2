#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX V2.4
Diagnostic sécurisé M1 à M5 et API.

Aucune collecte PMU.
Aucune publication.
Aucun FIGÉ automatique.
Aucune modification des archives.

Commande :
python -B verification_moteurs.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MOTEURS = ("m1", "m2", "m3", "m4", "m5")

TIMEOUT_SECONDS = 45


def verifier_fichier(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        print(
            f"[ABSENT] {path.relative_to(ROOT)}",
            flush=True
        )
        return False

    print(
        f"[PRESENT] {path.relative_to(ROOT)}",
        flush=True
    )
    return True


def executer_test(nom, arguments):
    environnement = os.environ.copy()

    environnement["PYTHONDONTWRITEBYTECODE"] = "1"
    environnement["PYTHONNOUSERSITE"] = "1"
    environnement["PYTHONUNBUFFERED"] = "1"

    try:
        resultat = subprocess.run(
            [sys.executable, "-B", *arguments],
            cwd=ROOT,
            env=environnement,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False
        )

    except subprocess.TimeoutExpired:
        print(f"[ECHEC] {nom} : délai dépassé")
        return False

    except (OSError, UnicodeError) as erreur:
        print(f"[ECHEC] {nom} : {erreur}")
        return False

    ok = resultat.returncode == 0

    print(
        f"[{'OK' if ok else 'ECHEC'}] {nom}",
        flush=True
    )

    if not ok:
        for sortie in (
            resultat.stdout,
            resultat.stderr
        ):
            if sortie.strip():
                print(sortie[-3000:])

    return ok


def main():
    print("=" * 55)
    print("X1000 PHOENIX V2.4")
    print("DIAGNOSTIC M1 A M5 + API")
    print("LECTURE SEULE — SANS PUBLICATION")
    print("=" * 55)

    fichiers = [
        ROOT / "api.py",
        ROOT / "moteurs" / "noyau_commun.py"
    ]

    fichiers += [
        ROOT / "moteurs" / f"{m}.py"
        for m in MOTEURS
    ]

    presents = {
        path: verifier_fichier(path)
        for path in fichiers
    }

    resultats = []

    for moteur in MOTEURS:
        chemin = ROOT / "moteurs" / f"{moteur}.py"

        ok = (
            presents[ROOT / "moteurs" / "noyau_commun.py"]
            and presents[chemin]
            and executer_test(
                moteur.upper(),
                ["-m", f"moteurs.{moteur}", "--self-test"]
            )
        )

        resultats.append((moteur.upper(), bool(ok)))

    api_ok = (
        presents[ROOT / "api.py"]
        and executer_test(
            "API",
            ["api.py", "--self-test"]
        )
    )

    resultats.append(("API", bool(api_ok)))

    reussis = sum(
        ok for _, ok in resultats
    )

    print("\n" + "=" * 55)
    print("BILAN FINAL")
    print("=" * 55)

    for nom, ok in resultats:
        print(
            f"{nom} : {'OK' if ok else 'ECHEC'}"
        )

    print(
        f"\nTests réussis : {reussis}/{len(resultats)}"
    )

    print("Aucune publication automatique.")
    print("Aucun FIGÉ automatique.")

    return 0 if reussis == len(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
