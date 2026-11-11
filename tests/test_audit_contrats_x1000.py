#!/usr/bin/env bash
set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
SOURCE="tests/test_audit_contrats_x1000.py"
DEST="scripts/audit_contrats_x1000.sh"

echo "=== X1000 PHOENIX - CORRECTION CONTROLEE ==="

test "$(basename "$(git rev-parse --show-toplevel)")" = \
  "x1000-intelligence-hippique-v2" || exit 1

test "$(git branch --show-current)" = "$BRANCHE" || {
  echo "ERREUR : branche non autorisee"
  exit 1
}

test -f "$SOURCE" || {
  echo "ERREUR : fichier source introuvable"
  exit 1
}

test ! -e "$DEST" || {
  echo "ERREUR : destination deja existante"
  exit 1
}

python - "$SOURCE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
contenu = p.read_text(encoding="utf-8-sig")
lignes = contenu.splitlines()

if not lignes or not lignes[0].startswith("#!"):
    raise SystemExit("ERREUR : en-tete Bash absent")

if not any(x in lignes[0] for x in ("bash", "sh")):
    raise SystemExit("ERREUR : script non reconnu comme shell")

print("Script shell identifie")
PY

mkdir -p scripts

bash -n "$SOURCE"

git mv "$SOURCE" "$DEST"
chmod +x "$DEST"

echo "=== CONTROLE SYNTAXE PYTHON ==="
python - <<'PY'
import ast
from pathlib import Path

fichiers = set()

for dossier in ("moteurs", "tests"):
    if Path(dossier).is_dir():
        fichiers.update(Path(dossier).rglob("*.py"))

for nom in (
    "api.py",
    "coordination_x1000.py",
    "integration_x1000.py",
    "validation_moteurs.py",
):
    p = Path(nom)
    if p.is_file():
        fichiers.add(p)

for fichier in sorted(fichiers):
    ast.parse(
        fichier.read_text(encoding="utf-8-sig"),
        filename=str(fichier)
    )
    print("OK :", fichier)

print("Syntaxe Python validee")
PY

echo "=== VERIFICATION BASH ==="
bash -n "$DEST"

echo "=== MODIFICATIONS LOCALES ==="
git status --short

echo "=== CORRECTION PREPAREE ==="
echo "Aucun commit, push, deploiement ou FIGE."
