#!/usr/bin/env bash
set -Eeuo pipefail

BRANCH="fix/x1000-v2-reparation-controlee"
FILE="test_coordination_x1000.py"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export TZ=Europe/Paris

echo "=== X1000 : diagnostic contrôlé ==="

command -v git >/dev/null
command -v python3 >/dev/null

cd "$(git rev-parse --show-toplevel)"

if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
    echo "ERREUR : branche incorrecte"
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERREUR : modifications locales présentes"
    exit 1
fi

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

echo "=== Vérification du fichier ==="

python3 -B - "$FILE" <<'PY'
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8-sig")

try:
    ast.parse(source)
    print("Python : syntaxe valide")
except SyntaxError as exc:
    print(f"Python : syntaxe invalide : {exc}")
PY

echo "=== Recherche d'une version Python ==="

FOUND=0

while IFS= read -r commit; do
    git show "$commit:$FILE" > "$TEMP/candidat.py" \
        2>/dev/null || continue

    if python3 -B - "$TEMP/candidat.py" <<'PY'
import ast
from pathlib import Path
ast.parse(Path(__import__("sys").argv[1]).read_text())
PY
    then
        echo "Version Python trouvée : $commit"
        cp "$TEMP/candidat.py" "$TEMP/test_coordination_x1000.py"
        FOUND=1
        break
    fi
done < <(git log --all --format=%H -- "$FILE")

if [[ "$FOUND" -eq 1 ]]; then
    echo "=== Vérification syntaxique ==="
    python3 -B - "$TEMP/test_coordination_x1000.py" <<'PY'
import ast
import sys
from pathlib import Path
ast.parse(Path(sys.argv[1]).read_text())
print("Syntaxe Python validée")
PY
else
    echo "Aucune ancienne version Python retrouvée"
    echo "Reconstruction des tests nécessaire"
fi

echo "=== CONTRÔLE TERMINÉ ==="
echo "Dépôt original inchangé"
echo "Aucun commit ni push"
echo "Aucun FIGÉ ni archive modifié"
echo "Aucune publication"
