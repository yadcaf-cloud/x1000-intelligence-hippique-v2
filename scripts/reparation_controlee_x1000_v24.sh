#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# X1000 V2.4 — REPARATION CONTROLEE ET AUDIT SECURISE
# ============================================================
# M1, M2, M3, M4, M5 et noyau commun
#
# - Aucune modification des fichiers originaux
# - Aucune modification des archives
# - Aucune collecte PMU
# - Aucune publication
# - Aucun FIGE automatique
# - Aucun commit ou push automatique
# - Aucun moteur execute
# - Copies de controle dans un dossier temporaire
# - Rapport JSON local
# ============================================================

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

umask 077

PYTHON="${PYTHON:-python3}"
EXPECTED="yadcaf-cloud/x1000-intelligence-hippique-v2"

info() {
    printf '\n[X1000] %s\n' "$*"
}

fail() {
    printf '\n[ERREUR] %s\n' "$*" >&2
    exit 1
}

# ============================================================
# 1. VERIFICATION DE L'ENVIRONNEMENT
# ============================================================

command -v git >/dev/null 2>&1 ||
    fail "Git introuvable"

command -v "$PYTHON" >/dev/null 2>&1 ||
    fail "Python introuvable"

"$PYTHON" -c \
    'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' ||
    fail "Python 3.9 minimum requis"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" ||
    fail "Depot Git introuvable"

cd "$ROOT"

REMOTE="$(git remote get-url origin 2>/dev/null)" ||
    fail "Remote origin absent"

case "$REMOTE" in
    "https://github.com/$EXPECTED"|\
    "https://github.com/$EXPECTED.git"|\
    "git@github.com:$EXPECTED"|\
    "git@github.com:$EXPECTED.git"|\
    "ssh://git@github.com/$EXPECTED"|\
    "ssh://git@github.com/$EXPECTED.git")
        info "Depot X1000 reconnu"
        ;;
    *)
        fail "Depot inattendu : $REMOTE"
        ;;
esac

# ============================================================
# 2. CONTROLE DE L'ETAT GIT
# ============================================================

info "Verification de l'etat Git"

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    fail "Depot non propre. Audit interrompu."
fi

info "Aucune modification locale detectee"

# ============================================================
# 3. CREATION D'UN ESPACE ISOLE
# ============================================================

TMP_BASE="${TMPDIR:-/tmp}"

[[ -d "$TMP_BASE" ]] ||
    fail "Dossier temporaire introuvable"

TMP_BASE="$(cd "$TMP_BASE" && pwd -P)"

case "$TMP_BASE/" in
    "$ROOT/"*)
        fail "Dossier temporaire situe dans le depot"
        ;;
esac

WORK="$(mktemp -d "$TMP_BASE/x1000-v24-audit.XXXXXXXX")" ||
    fail "Creation du dossier isole impossible"

mkdir -p "$WORK/moteurs"

info "Dossier de controle : $WORK"

# ============================================================
# 4. AUDIT STATIQUE DES SIX MODULES
# ============================================================

"$PYTHON" -B - "$ROOT" "$WORK" <<'PY'
from pathlib import Path
import ast
import hashlib
import json
import shutil
import sys

root = Path(sys.argv[1]).resolve()
work = Path(sys.argv[2]).resolve()

modules = [
    "m1",
    "m2",
    "m3",
    "m4",
    "m5",
    "noyau_commun",
]

ignored = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}

report = {
    "application": "X1000",
    "version": "2.4",
    "type": "AUDIT_STATIQUE_SECURISÉ",
    "mode": "LECTURE_SEULE_DEPOT",
    "collecte_pmu": False,
    "publication": False,
    "fige_automatique": False,
    "execution_moteurs": False,
    "modification_archives": False,
    "validation_officielle": False,
    "modules": [],
    "errors": [],
    "warnings": [],
}

def sha256(data):
    return hashlib.sha256(data).hexdigest()

for name in modules:
    candidates = []

    for path in root.rglob("*.py"):
        relative = path.relative_to(root)

        if any(part in ignored for part in relative.parts):
            continue

        if path.is_symlink() or not path.is_file():
            continue

        if path.stem.strip() == name:
            candidates.append(path)

    candidates.sort(
        key=lambda p: str(p.relative_to(root))
    )

    entry = {
        "name": name,
        "candidates": [
            str(p.relative_to(root))
            for p in candidates
        ],
    }

    if len(candidates) != 1:
        entry["status"] = "SOURCE_AMBIGUE_OU_ABSENTE"
        report["errors"].append(
            f"{name}: {len(candidates)} source(s)"
        )
        report["modules"].append(entry)
        continue

    source = candidates[0]
    destination = work / "moteurs" / f"{name}.py"

    try:
        if not source.resolve().is_relative_to(root):
            raise ValueError("Source hors depot")

        data = source.read_bytes()

        # Analyse syntaxique sans execution.
        compile(data, str(source), "exec")

        tree = ast.parse(
            data,
            filename=str(source),
        )

        shutil.copyfile(source, destination)

        copied = destination.read_bytes()

        if sha256(data) != sha256(copied):
            raise ValueError("Copie non conforme")

        functions = sorted(
            node.name
            for node in tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        )

        entry.update({
            "status": "SYNTAXE_OK",
            "source": str(source.relative_to(root)),
            "sha256": sha256(data),
            "copy": str(destination),
            "functions": functions,
        })

        if (
            name != "noyau_commun"
            and "analyser_course" not in functions
        ):
            report["warnings"].append(
                f"{name}: fonction analyser_course "
                "non detectee au niveau principal"
            )

    except (
        OSError,
        SyntaxError,
        UnicodeError,
        ValueError,
    ) as exc:
        entry["status"] = "ERREUR"
        entry["error"] = str(exc)

        report["errors"].append(
            f"{name}: {exc}"
        )

    report["modules"].append(entry)

report["status"] = (
    "CONTROLE_STATIQUE_REUSSI"
    if not report["errors"]
    else "CORRECTIONS_NECESSAIRES"
)

rapport = work / "rapport_audit_v24.json"

rapport.write_text(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    )
)

print(f"\nRAPPORT_JSON={rapport}")

sys.exit(
    0 if not report["errors"] else 1
)
PY

# ============================================================
# 5. CONTROLE FINAL DU DEPOT
# ============================================================

info "Verification finale Git"

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    fail "Modification locale detectee pendant l'audit"
fi

# ============================================================
# 6. RESULTAT FINAL
# ============================================================

printf '\n============================================\n'
printf 'X1000 V2.4 — AUDIT STATIQUE TERMINE\n'
printf '============================================\n'
printf 'Moteurs : M1, M2, M3, M4, M5\n'
printf 'Noyau commun : controle\n'
printf 'Originaux : preserves\n'
printf 'Archives : non modifiees\n'
printf 'Collecte PMU : aucune\n'
printf 'Publication : aucune\n'
printf 'FIGE automatique : aucun\n'
printf 'Execution moteurs : aucune\n'
printf 'Commit : aucun\n'
printf 'Push : aucun\n'
printf 'Fusion : aucune\n'
printf '============================================\n'

info "Examiner le rapport avant toute correction."
