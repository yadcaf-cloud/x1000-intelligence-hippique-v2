#!/usr/bin/env bash
set -euo pipefail

echo "=== X1000 PHOENIX - REPARATION CONTROLEE ==="

BRANCHE="fix/x1000-v2-reparation-controlee"
ANCIEN="tests/test_audit_contrats_x1000.py"
NOUVEAU="scripts/renommage_controle_x1000.sh"

if [ "$(git branch --show-current)" != "$BRANCHE" ]; then
    echo "ERREUR : branche non autorisee"
    exit 1
fi

if [ ! -f "$ANCIEN" ]; then
    echo "ERREUR : fichier source introuvable"
    exit 1
fi

if [ -e "$NOUVEAU" ]; then
    echo "ERREUR : destination deja utilisee"
    exit 1
fi

mkdir -p scripts
git mv "$ANCIEN" "$NOUVEAU"

echo "=== VERIFICATION BASH ==="
bash -n "$NOUVEAU"

echo "=== VERIFICATION PYTHON ==="
python -m compileall -q moteurs tests

echo "=== TESTS ==="
python -m pytest -q --import-mode=importlib

echo "=== ETAT GIT ==="
git status --short

echo "AUCUN COMMIT, PUSH, DEPLOIEMENT OU FIGE"
