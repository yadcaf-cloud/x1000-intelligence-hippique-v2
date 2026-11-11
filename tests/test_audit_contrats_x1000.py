#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo " X1000 PHOENIX - REPARATION CONTROLEE"
echo "========================================"

BRANCHE="fix/x1000-v2-reparation-controlee"
DEPOT="x1000-intelligence-hippique-v2"

ANCIEN="tests/test_audit_contrats_x1000.py"
NOUVEAU="scripts/renommage_controle_x1000.sh"

echo "=== CONTROLE DU DEPOT ==="

RACINE="$(git rev-parse --show-toplevel)"
cd "$RACINE"

if [ "$(basename "$RACINE")" != "$DEPOT" ]; then
    echo "ERREUR : depot non autorise"
    exit 1
fi

if [ "$(git branch --show-current)" != "$BRANCHE" ]; then
    echo "ERREUR : branche non autorisee"
    exit 1
fi

echo "Depot et branche verifies."

echo "=== CONTROLE DES FICHIERS ==="

if [ -f "$ANCIEN" ]; then

    if [ -e "$NOUVEAU" ]; then
        echo "ERREUR : destination deja utilisee"
        exit 1
    fi

    # Verifier que le fichier est bien un script Bash
    if ! head -n 1 "$ANCIEN" | grep -q 'bash'; then
        echo "ERREUR : source non reconnue comme Bash"
        exit 1
    fi

    bash -n "$ANCIEN"

    mkdir -p scripts
    git mv "$ANCIEN" "$NOUVEAU"

    echo "Script Bash deplace correctement."

elif [ -f "$NOUVEAU" ]; then

    echo "Script deja deplace."

else

    echo "ERREUR : aucun fichier source trouve"
    exit 1

fi

echo "=== VERIFICATION BASH ==="

bash -n "$NOUVEAU"

echo "Syntaxe Bash valide."

echo "=== VERIFICATION PYTHON ==="

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.
export X1000_READ_ONLY=1
export X1000_NO_FIGE=1
export X1000_NO_PUBLICATION=1

python - <<'PY'
import ast
from pathlib import Path

for dossier in ("moteurs", "tests"):
    chemin = Path(dossier)

    if not chemin.is_dir():
        raise SystemExit(
            f"ERREUR : dossier absent : {dossier}"
        )

    for fichier in chemin.rglob("*.py"):
        ast.parse(
            fichier.read_text(encoding="utf-8"),
            filename=str(fichier)
        )
        print(f"OK : {fichier}")

print("Syntaxe Python valide.")
PY

echo "=== TESTS PYTHON ==="

if python -m pytest --version >/dev/null 2>&1; then

    python -m pytest -q \
        --import-mode=importlib \
        -p no:cacheprovider

else

    echo "ERREUR : pytest non installe"
    exit 1

fi

echo "=== ETAT GIT ==="

git status --short

echo "========================================"
echo " REPARATION LOCALE TERMINEE"
echo " Aucun commit automatique"
echo " Aucun push automatique"
echo " Aucun deploiement automatique"
echo " Aucun FIGE cree"
echo "========================================"
