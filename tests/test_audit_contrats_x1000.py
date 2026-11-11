#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo " X1000 PHOENIX - REPARATION 1/6"
echo " DIAGNOSTIC M1 A M5"
echo "======================================"

BRANCHE="fix/x1000-v2-reparation-controlee"
DEPOT="x1000-intelligence-hippique-v2"

SOURCE="tests/test_audit_contrats_x1000.py"
DEST="scripts/renommage_controle_x1000.sh"

RACINE="$(git rev-parse --show-toplevel)"
cd "$RACINE"

# SECURITE
if [[ "$(basename "$RACINE")" != "$DEPOT" ]]; then
    echo "ERREUR : depot incorrect"
    exit 1
fi

if [[ "$(git branch --show-current)" != "$BRANCHE" ]]; then
    echo "ERREUR : branche incorrecte"
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERREUR : modifications locales presentes"
    echo "Sauvegardez-les avant de continuer."
    exit 1
fi

if [[ ! -f "$SOURCE" ]]; then
    echo "ERREUR : fichier source absent"
    exit 1
fi

if [[ -e "$DEST" ]]; then
    echo "ERREUR : destination deja existante"
    exit 1
fi

# VERIFIER LA NATURE DU FICHIER
if ! head -n 1 "$SOURCE" | grep -q 'bash'; then
    echo "ERREUR : source non reconnue comme Bash"
    exit 1
fi

bash -n "$SOURCE"

# RECHERCHER UNE VERSION PYTHON ANTERIEURE
echo "Recherche du test Python original..."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

TROUVE=0

while IFS= read -r REV; do
    if git show "$REV:$SOURCE" \
        > "$TMP/test.py" 2>/dev/null; then

        if python - "$TMP/test.py" <<'PY'
import ast
import sys
from pathlib import Path

p = Path(sys.argv[1])

try:
    source = p.read_text(encoding="utf-8")
    tree = ast.parse(source)

    if not any(
        isinstance(n, (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef
        )) and (
            n.name.startswith("test_")
            or n.name.startswith("Test")
        )
        for n in tree.body
    ):
        raise ValueError("Aucun test identifiable")

except (SyntaxError, ValueError, UnicodeError):
    sys.exit(1)
PY
        then
            TROUVE=1
            echo "Version Python candidate : $REV"
            break
        fi
    fi
done < <(git log --format=%H --all -- "$SOURCE")

if [[ "$TROUVE" -ne 1 ]]; then
    echo "ERREUR : aucun test Python valide trouve"
    echo "Aucune modification effectuee."
    exit 1
fi

# DEPLACEMENT DU SCRIPT BASH
mkdir -p scripts
git mv "$SOURCE" "$DEST"

# RESTAURATION DU TEST PYTHON
cp "$TMP/test.py" "$SOURCE"

# VERIFICATIONS
echo "=== SYNTAXE BASH ==="
bash -n "$DEST"

echo "=== SYNTAXE PYTHON ==="
python - "$SOURCE" <<'PY'
import ast
import sys
from pathlib import Path

p = Path(sys.argv[1])
ast.parse(
    p.read_text(encoding="utf-8"),
    filename=str(p)
)
print("Syntaxe Python valide")
PY

echo "=== TESTS DIAGNOSTIC ==="

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.
export X1000_READ_ONLY=1
export X1000_NO_FIGE=1
export X1000_NO_PUBLICATION=1

python -m unittest discover \
    -s tests \
    -p "test_audit_contrats_x1000.py" \
    -v

echo "=== ETAT GIT ==="
git status --short

echo "======================================"
echo " REPARATION LOCALE TERMINEE"
echo " Aucun commit"
echo " Aucun push"
echo " Aucun deploiement"
echo " Aucun FIGE cree par le script"
echo "======================================"
