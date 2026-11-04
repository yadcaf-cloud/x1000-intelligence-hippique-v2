
#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.4 — REPARATION CONTROLEE
# Audit et copies isolees uniquement.
# Aucun commit, push, FIGE ou publication.
# Aucun moteur execute.

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
umask 077

PYTHON="${PYTHON:-python3}"
EXPECTED="yadcaf-cloud/x1000-intelligence-hippique-v2"

info() {
    printf '[X1000] %s\n' "$*"
}

fail() {
    printf '[ERREUR] %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null ||
    fail "Git introuvable"

command -v "$PYTHON" >/dev/null ||
    fail "Python introuvable"

"$PYTHON" -c \
    'import sys; assert sys.version_info >= (3, 9)' ||
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
        ;;
    *)
        fail "Depot inattendu : $REMOTE"
        ;;
esac

if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
    fail "Depot non propre. Aucun changement effectue."
fi

TMP_BASE="${TMPDIR:-/tmp}"

[[ -d "$TMP_BASE" ]] ||
    fail "Dossier temporaire introuvable"

TMP_BASE="$(cd "$TMP_BASE" && pwd -P)"

case "$TMP_BASE/" in
    "$ROOT/"*)
        fail "Dossier temporaire dans le depot"
        ;;
esac

WORK="$(mktemp -d "$TMP_BASE/x1000-v24-audit.XXXXXXXX")" ||
    fail "Creation du dossier isole impossible"

mkdir -p "$WORK/moteurs"

info "Audit isole : $WORK"

"$PYTHON" -B - "$ROOT" "$WORK" <<'PY'
from pathlib import Path
import ast
import hashlib
import json
import shutil
import sys

root = Path(sys.argv[1]).resolve()
work = Path(sys.argv[2]).resolve()

names = [
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
    "version": "2.4",
    "mode": "AUDIT_ISOLE_SANS_EXECUTION",
    "modules": [],
    "errors": [],
    "warnings": [],
}

for name in names:
    candidates = []

    for path in root.rglob("*.py"):
        if any(
            part in ignored
            for part in path.relative_to(root).parts
        ):
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
        entry["status"] = "AMBIGU"
        report["errors"].append(
            f"{name}: {len(candidates)} source(s)"
        )
        report["modules"].append(entry)
        continue

    src = candidates[0]
    dest = work / "moteurs" / (name + ".py")

    try:
        if not src.resolve().is_relative_to(root):
            raise ValueError("Source hors depot")

        data = src.read_bytes()

        # Verification sans execution.
        compile(data, str(src), "exec")

        shutil.copyfile(src, dest)

        def sha256(content):
            return hashlib.sha256(content).hexdigest()

        if sha256(data) != sha256(dest.read_bytes()):
            raise ValueError("Copie non conforme")

        tree = ast.parse(
            data,
            filename=str(src),
        )

        functions = sorted(
            node.name
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        )

        entry.update({
            "status": "SYNTAXE_OK",
            "sha256": sha256(data),
            "functions": functions,
            "copy": str(dest),
        })

        if (
            name != "noyau_commun"
            and "analyser_course" not in functions
        ):
            report["warnings"].append(
                f"{name}: contrat analyser_course "
                "a confirmer"
            )

    except (
        OSError,
        SyntaxError,
        ValueError,
        UnicodeError,
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

path = work / "rapport_audit_v24.json"

path.write_text(
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

print(f"\nRAPPORT : {path}")

sys.exit(
    0 if not report["errors"] else 1
)
PY

info "Audit statique termine."
info "Originaux preserves."
info "Archives non modifiees."
info "Aucun moteur execute."
info "Aucun FIGE cree."
info "Aucun commit."
info "Aucun push."
info "Aucune publication."
