#!/bin/bash

set -e

cd ~/x1000-intelligence-hippique-v2 || exit 1

echo "=== X1000 PHOENIX - RENOMMAGE CONTROLE ==="

BRANCHE="fix/x1000-v2-reparation-controlee"

if [ "$(git branch --show-current)" != "$BRANCHE" ]; then
    echo "ERREUR : branche non autorisee"
    exit 1
fi

ANCIEN="tests/test_audit_contrats_x1000.py"
NOUVEAU="tests/test_audit_moteurs_m1_m5_synthetique.py"

if [ ! -f "$ANCIEN" ]; then
    echo "ERREUR : fichier original introuvable"
    exit 1
fi

if [ -e "$NOUVEAU" ]; then
    echo "ERREUR : nouveau nom deja utilise"
    exit 1
fi

git mv "$ANCIEN" "$NOUVEAU"

echo "=== VERIFICATION SYNTAXE ==="
python -m py_compile "$NOUVEAU"

echo "=== TESTS PYTEST ==="
python -m pytest -q --import-mode=importlib
RESULTAT=$?

echo "=== ETAT GIT ==="
git status --short

echo "Code retour Pytest : $RESULTAT"
echo "AUCUN COMMIT, PUSH OU DEPLOIEMENT"
