#!/usr/bin/env bash
set -euo pipefail

# Depot X1000 V2
# Executer depuis la racine du depot.

SOURCE="fcc9bf3c74"
BRANCHE="fix/restauration-m1-m5"

# Eviter d'ecraser des changements locaux.
if [ -n "$(git status --porcelain)" ]; then
  echo "ERREUR : modifications locales presentes."
  exit 1
fi

git switch main
git fetch origin main
git pull --ff-only origin main

# Branche de restauration.
git switch -c "$BRANCHE"

# Restaurer les cinq versions originales.
git restore --source="$SOURCE" -- \
  "m1.py " \
  "m2.py " \
  "m3.py " \
  "m4.py" \
  "m5.py"

# Corriger uniquement les noms.
git mv "m1.py " "m1.py"
git mv "m2.py " "m2.py"
git mv "m3.py " "m3.py"

# Comparer les contenus aux originaux.
for numero in 1 2 3 4 5; do
  original="m${numero}.py"

  if [ "$numero" -le 3 ]; then
    original="${original} "
  fi

  attendu=$(git rev-parse "${SOURCE}:${original}")
  actuel=$(git hash-object "m${numero}.py")

  if [ "$attendu" != "$actuel" ]; then
    echo "ERREUR : contenu M${numero} modifie."
    exit 1
  fi

  echo "M${numero} : contenu original preserve."
done

# Verification syntaxique sans fichiers pyc.
python - <<'PY'
import ast
from pathlib import Path

for numero in range(1, 6):
    chemin = Path(f"m{numero}.py")
    ast.parse(
        chemin.read_text(encoding="utf-8"),
        filename=str(chemin),
    )
    print(f"M{numero} : syntaxe valide")
PY

# Afficher les modifications sans depot.
git status --short
git diff --stat HEAD

echo "Restauration preparee."
echo "Aucun commit ni push effectue."
