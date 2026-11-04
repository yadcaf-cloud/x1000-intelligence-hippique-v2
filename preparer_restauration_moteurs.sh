#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 PHOENIX — RESTAURATION CONTROLEE M1 A M5
# Aucun commit, aucun push, aucune publication.

echo "=== X1000 : VERIFICATION DU DEPOT ==="

git rev-parse --is-inside-work-tree >/dev/null
cd "$(git rev-parse --show-toplevel)"

# Refuser toute modification locale preexistante.
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
    echo "ERREUR : depot local non propre."
    exit 1
fi

# Verifier que le script officiel est present.
if [ ! -f restaurer_moteurs.sh ]; then
    echo "ERREUR : restaurer_moteurs.sh absent."
    exit 1
fi

# Executer la restauration deja prevue dans le depot.
bash restaurer_moteurs.sh

echo "=== DIAGNOSTIC M1 A M5 ==="

python -B verification_moteurs.py

echo "=== CONTROLE DES MODIFICATIONS ==="

git status --short
git diff --cached --check
git diff --check

echo "=== FIN DE LA VERIFICATION ==="
echo "Aucun commit ni push automatique."
