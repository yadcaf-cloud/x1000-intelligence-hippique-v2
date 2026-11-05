#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 - Reparation controlee
# Aucun commit, push, FIGE ou deploiement.

BRANCH="fix/x1000-v2-reparation-controlee"
SOURCE="40ee2ef330ce"
FICHIER="test_validation_moteurs.py"

erreur() {
  echo "ERREUR : $*" >&2
  exit 1
}

command -v git >/dev/null || erreur "Git absent"
command -v python3 >/dev/null || erreur "Python absent"

cd "$(git rev-parse --show-toplevel)"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
  erreur "Branche non autorisee"

[[ -z "$(git status --porcelain)" ]] ||
  erreur "Depot non propre : annulation"

git cat-file -e "${SOURCE}:${FICHIER}" ||
  erreur "Version historique introuvable"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

mkdir -p "$TEMP/depot"

git archive HEAD | tar -x -C "$TEMP/depot"

git show "${SOURCE}:${FICHIER}" \
  > "$TEMP/depot/$FICHIER"

export X1000_TEST_FILE="$TEMP/depot/$FICHIER"

python3 -B - <<'PY'
import ast
import os
from pathlib import Path

fichier = Path(os.environ["X1000_TEST_FILE"])
source = fichier.read_text(encoding="utf-8")
arbre = ast.parse(source)

classes = [
    n for n in arbre.body
    if isinstance(n, ast.ClassDef)
    and n.name == "TestsSecuriteX1000"
]

if len(classes) != 1:
    raise SystemExit("Classe de tests introuvable")

classe = classes[0]

tests = [
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(tests) < 55:
    raise SystemExit("Moins de 55 tests")

methodes = [
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name == "verifier_prediction_rejetee"
]

if len(methodes) != 1:
    raise SystemExit("Methode auxiliaire invalide")

methode = methodes[0]
lignes = source.splitlines(keepends=True)
indent = " " * methode.col_offset

nouvelle = f'''{indent}def verifier_prediction_rejetee(
{indent}    self,
{indent}    moteur,
{indent}    positions,
{indent}    actifs=Ellipsis,
{indent}):
{indent}    """Verifier le rejet des predictions."""
{indent}    if actifs is Ellipsis:
{indent}        actifs = set(range(1, 7))

{indent}    with self.assertRaises(
{indent}        self.ValidationErreur
{indent}    ):
{indent}        self.valider_prediction(
{indent}            moteur,
{indent}            positions,
{indent}            actifs,
{indent}        )
'''

lignes[
    methode.lineno - 1:methode.end_lineno
] = [nouvelle]

resultat = "".join(lignes)
ast.parse(resultat, filename=str(fichier))

fichier.write_text(resultat, encoding="utf-8")

print("55 tests minimum preserves")
print("Correction actifs=None appliquee")
print("Syntaxe Python valide")
PY

echo "=== TESTS EN COPIE TEMPORAIRE ==="

(
  cd "$TEMP/depot"
  python3 -B test_validation_moteurs.py
  python3 -B test_coordination_x1000.py
)

echo "=== INSTALLATION CONTROLEE ==="

[[ -z "$(git status --porcelain)" ]] ||
  erreur "Depot modifie pendant les tests"

cp "$TEMP/depot/$FICHIER" "$FICHIER"

python3 -B - <<'PY'
import ast
from pathlib import Path

fichier = Path("test_validation_moteurs.py")
ast.parse(
    fichier.read_text(encoding="utf-8"),
    filename=str(fichier),
)
print("Syntaxe finale : OK")
PY

git diff --check
git status --short

echo "=== REPARATION TERMINEE ==="
echo "Fichier corrige : $FICHIER"
echo "Aucun commit ni push"
echo "Aucune publication"
echo "Aucun FIGE"
echo "Aucune archive modifiee"
