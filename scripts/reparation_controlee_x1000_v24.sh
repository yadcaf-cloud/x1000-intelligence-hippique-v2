#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# X1000 V2.4 - REPARATION CONTROLEE M1 A M5
# ============================================================
# - Aucun ecrasement des fichiers originaux
# - Aucune modification des archives
# - Aucune collecte PMU
# - Aucune publication
# - Aucun FIGE
# - Aucun commit ou push automatique
# - Arret immediat en cas d'anomalie
# ============================================================

DEPOT="yadcaf-cloud/x1000-intelligence-hippique-v2"
BRANCHE="fix/audit-general-x1000-v24"
PYTHON="${PYTHON:-python3}"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

erreur() {
    printf '\nERREUR : %s\n' "$*" >&2
    exit 1
}

info() {
    printf '\n[X1000] %s\n' "$*"
}

# ============================================================
# 1. CONTROLE DE L'ENVIRONNEMENT
# ============================================================

command -v git >/dev/null ||
    erreur "Git indisponible"

command -v "$PYTHON" >/dev/null ||
    erreur "Python 3 indisponible"

git rev-parse --show-toplevel >/dev/null 2>&1 ||
    erreur "Ce dossier n'est pas un depot Git"

RACINE="$(git rev-parse --show-toplevel)"
cd "$RACINE"

REPO_ACTUEL="$(git remote get-url origin 2>/dev/null || true)"

case "$REPO_ACTUEL" in
    *github.com/yadcaf-cloud/x1000-intelligence-hippique-v2* )
        ;;
    *)
        erreur "Depot GitHub inattendu : $REPO_ACTUEL"
        ;;
esac

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    erreur "Depot non propre. Sauvegarder les modifications avant execution."
fi

git check-ref-format --branch "$BRANCHE" >/dev/null ||
    erreur "Nom de branche invalide"

if git show-ref --verify --quiet "refs/heads/$BRANCHE"; then
    erreur "La branche de reparation existe deja"
fi

info "Verification des originaux"

# Les espaces finaux font partie des noms originaux.
SOURCES=(
    "m1.py "
    "m2.py "
    "m3.py "
    "m4.py"
    "m5.py "
    "noyau_commun.py"
)

DESTINATIONS=(
    "moteurs/m1.py"
    "moteurs/m2.py"
    "moteurs/m3.py"
    "moteurs/m4.py"
    "moteurs/m5.py"
    "moteurs/noyau_commun.py"
)

for i in "${!SOURCES[@]}"; do
    source="${SOURCES[$i]}"
    destination="${DESTINATIONS[$i]}"

    [[ -f "$source" ]] ||
        erreur "Original absent : <$source>"

    [[ ! -e "$destination" ]] ||
        erreur "Destination deja existante : $destination"
done

[[ ! -e "moteurs/__init__.py" ]] ||
    erreur "Package moteurs deja present"

[[ ! -e "verification_moteurs_v24.py" ]] ||
    erreur "Diagnostic V2.4 deja present"

# ============================================================
# 2. CREATION DE LA BRANCHE
# ============================================================

info "Creation de la branche de reparation"

git switch -c "$BRANCHE"

# ============================================================
# 3. RESTAURATION NON DESTRUCTIVE
# ============================================================

info "Creation des copies normalisees"

mkdir -p moteurs

for i in "${!SOURCES[@]}"; do
    source="${SOURCES[$i]}"
    destination="${DESTINATIONS[$i]}"

    cp -- "$source" "$destination"

    hash_source="$(git hash-object -- "$source")"
    hash_copie="$(git hash-object -- "$destination")"

    [[ "$hash_source" == "$hash_copie" ]] ||
        erreur "Copie non conforme : $destination"

    printf 'OK : <%s> -> <%s>\n' \
        "$source" "$destination"
done

cat > moteurs/__init__.py <<'PY'
"""
X1000 V2.4 - Package des cinq moteurs.

Copies de travail des modules originaux.
Aucune collecte, publication ou validation automatique.
"""

VERSION = "2.4"
PY

# ============================================================
# 4. DIAGNOSTIC GENERAL RENFORCE
# ============================================================

info "Installation du diagnostic technique"

cat > verification_moteurs_v24.py <<'PY'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - Audit technique M1 a M5.

Lecture seule :
- Controle des fichiers et des imports.
- Controle de la syntaxe Python.
- Verification du contrat commun.
- Verification des cinq autotests.

Aucune donnee PMU.
Aucune publication.
Aucun FIGE.
Aucune modification des archives.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
import subprocess
import sys

from pathlib import Path


RACINE = Path(__file__).resolve().parent
PACKAGE = RACINE / "moteurs"

MOTEURS = ("m1", "m2", "m3", "m4", "m5")

SOURCES = {
    "m1": "m1.py ",
    "m2": "m2.py ",
    "m3": "m3.py ",
    "m4": "m4.py",
    "m5": "m5.py ",
    "noyau_commun": "noyau_commun.py",
}


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()

    with chemin.open("rb") as fichier:
        for bloc in iter(
            lambda: fichier.read(65536),
            b"",
        ):
            h.update(bloc)

    return h.hexdigest()


def controler_fichier(nom: str) -> dict:
    original = RACINE / SOURCES[nom]
    copie = PACKAGE / (nom + ".py")

    resultat = {
        "nom": nom,
        "original_present": original.is_file(),
        "copie_presente": copie.is_file(),
        "copie_identique": False,
        "syntaxe_valide": False,
        "anomalies": [],
    }

    if not original.is_file():
        resultat["anomalies"].append(
            "Original absent"
        )
        return resultat

    if not copie.is_file():
        resultat["anomalies"].append(
            "Copie absente"
        )
        return resultat

    resultat["copie_identique"] = (
        sha256(original) == sha256(copie)
    )

    if not resultat["copie_identique"]:
        resultat["anomalies"].append(
            "Copie differente de l'original"
        )

    try:
        source = copie.read_text(
            encoding="utf-8"
        )

        arbre = ast.parse(
            source,
            filename=str(copie),
        )

        compile(
            arbre,
            str(copie),
            "exec",
        )

        resultat["syntaxe_valide"] = True

        if nom != "noyau_commun":
            fonctions = {
                noeud.name
                for noeud in arbre.body
                if isinstance(
                    noeud,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
            }

            if "analyser_course" not in fonctions:
                resultat["anomalies"].append(
                    "analyser_course absente"
                )

    except (
        SyntaxError,
        OSError,
        UnicodeError,
        ValueError,
    ) as erreur:
        resultat["anomalies"].append(
            f"Erreur de syntaxe : {erreur}"
        )

    return resultat


def verifier_import(nom: str) -> dict:
    module = f"moteurs.{nom}"

    resultat = {
        "module": module,
        "import_reussi": False,
        "version": None,
        "analyser_course": False,
        "erreur": None,
    }

    try:
        importe = importlib.import_module(
            module
        )

        resultat["import_reussi"] = True
        resultat["version"] = getattr(
            importe,
            "VERSION",
            None,
        )

        resultat["analyser_course"] = callable(
            getattr(
                importe,
                "analyser_course",
                None,
            )
        )

    except Exception as erreur:
        resultat["erreur"] = (
            f"{type(erreur).__name__}: {erreur}"
        )

    return resultat


def verifier_autotest(nom: str) -> dict:
    module = f"moteurs.{nom}"

    environnement = os.environ.copy()
    environnement["PYTHONDONTWRITEBYTECODE"] = "1"
    environnement["PYTHONNOUSERSITE"] = "1"

    try:
        processus = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                module,
                "--self-test",
            ],
            cwd=RACINE,
            env=environnement,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        return {
            "module": module,
            "code_retour": processus.returncode,
            "reussi": processus.returncode == 0,
            "stdout": processus.stdout[-3000:],
            "stderr": processus.stderr[-3000:],
        }

    except (
        OSError,
        subprocess.TimeoutExpired,
    ) as erreur:
        return {
            "module": module,
            "code_retour": None,
            "reussi": False,
            "erreur": str(erreur),
        }


def main() -> int:
    noms = (*MOTEURS, "noyau_commun")

    fichiers = [
        controler_fichier(nom)
        for nom in noms
    ]

    imports = [
        verifier_import(nom)
        for nom in noms
    ]

    autotests = [
        verifier_autotest(nom)
        for nom in MOTEURS
    ]

    fichiers_ok = all(
        item["original_present"]
        and item["copie_presente"]
        and item["copie_identique"]
        and item["syntaxe_valide"]
        and not item["anomalies"]
        for item in fichiers
    )

    imports_ok = all(
        item["import_reussi"]
        and item["version"] == "2.4"
        and (
            item["module"] == "moteurs.noyau_commun"
            or item["analyser_course"]
        )
        for item in imports
    )

    autotests_ok = all(
        item["reussi"]
        for item in autotests
    )

    conforme = (
        fichiers_ok
        and imports_ok
        and autotests_ok
    )

    rapport = {
        "application": "X1000 V2.4",
        "type": "AUDIT_TECHNIQUE",
        "statut": (
            "CONTROLES_TECHNIQUES_REUSSIS"
            if conforme
            else "CORRECTIONS_NECESSAIRES"
        ),
        "lecture_seule": True,
        "collecte_pmu": False,
        "publication": False,
        "fige_automatique": False,
        "modification_archives": False,
        "validation_officielle_pmu": False,
        "fichiers": fichiers,
        "imports": imports,
        "autotests": autotests,
    }

    print(
        json.dumps(
            rapport,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if conforme else 1


if __name__ == "__main__":
    raise SystemExit(main())
PY

# ============================================================
# 5. VERIFICATION DE SYNTAXE SANS PYC
# ============================================================

info "Verification de syntaxe"

"$PYTHON" -B - <<'PY'
from pathlib import Path

fichiers = [
    *sorted(Path("moteurs").glob("*.py")),
    Path("verification_moteurs_v24.py"),
]

for fichier in fichiers:
    source = fichier.read_bytes()
    compile(source, str(fichier), "exec")
    print(f"SYNTAXE OK : {fichier}")
PY

# ============================================================
# 6. AUDIT GENERAL ET AUTOTESTS
# ============================================================

info "Execution du diagnostic M1-M5"

"$PYTHON" -B verification_moteurs_v24.py

# ============================================================
# 7. CONTROLE FINAL DES ORIGINAUX
# ============================================================

info "Verification de l'integrite des originaux"

for i in "${!SOURCES[@]}"; do
    source="${SOURCES[$i]}"

    git diff --quiet HEAD -- "$source" ||
        erreur "Original modifie : $source"

    git diff --cached --quiet HEAD -- "$source" ||
        erreur "Original indexe comme modifie : $source"
done

# Aucune modification suivie ne doit exister.
git diff --quiet HEAD ||
    erreur "Un fichier suivi a ete modifie"

git diff --cached --quiet HEAD ||
    erreur "Une modification indexee a ete detectee"

info "Fichiers nouveaux"

git status --short --untracked-files=all

# ============================================================
# 8. RESULTAT
# ============================================================

printf '\n========================================\n'
printf 'X1000 V2.4 - REPARATION PREPAREE\n'
printf '========================================\n'
printf 'Branche : %s\n' "$BRANCHE"
printf 'Originaux : preserves\n'
printf 'Archives : non modifiees\n'
printf 'Collecte PMU : aucune\n'
printf 'Publication : aucune\n'
printf 'FIGE automatique : aucun\n'
printf 'Commit : aucun\n'
printf 'Push : aucun\n'
printf 'Fusion : aucune\n'
printf '========================================\n'

printf '\nEtapes suivantes :\n'
printf '1. Examiner les nouveaux fichiers.\n'
printf '2. Examiner le rapport du diagnostic.\n'
printf '3. Corriger toute incompatibilite detectee.\n'
printf '4. Faire valider les tests avant commit.\n'
