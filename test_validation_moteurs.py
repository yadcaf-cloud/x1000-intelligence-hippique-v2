#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 - Reparation controlee des tests
# Aucun commit, push, deploiement ou FIGE.

BRANCH="fix/x1000-v2-reparation-controlee"
FICHIER="test_validation_moteurs.py"

erreur() {
  echo "ERREUR : $*" >&2
  exit 1
}

command -v git >/dev/null || erreur "Git absent"
command -v python3 >/dev/null || erreur "Python absent"

cd "$(git rev-parse --show-toplevel)"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
  erreur "Branche incorrecte"

[[ -z "$(git status --porcelain)" ]] ||
  erreur "Depot non propre : intervention annulee"

export PYTHONDONTWRITEBYTECODE=1

python3 -B - <<'PY'
import ast
import subprocess
from pathlib import Path

fichier = Path("test_validation_moteurs.py")

def git(*args):
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

# Retrouver une version complete dans l'historique.
commits = git(
    "rev-list", "--all", "--", str(fichier)
).splitlines()

source = None
reference = None

for commit in commits:
    resultat = subprocess.run(
        ["git", "show", f"{commit}:{fichier}"],
        capture_output=True,
        text=True,
    )
    if resultat.returncode:
        continue

    candidat = resultat.stdout

    try:
        arbre = ast.parse(candidat)
    except SyntaxError:
        continue

    classes = [
        n for n in arbre.body
        if isinstance(n, ast.ClassDef)
        and n.name == "TestsSecuriteX1000"
    ]

    if not classes:
        continue

    classe = classes[0]
    tests = [
        n for n in classe.body
        if isinstance(n, ast.FunctionDef)
        and n.name.startswith("test_")
    ]

    auxiliaires = [
        n for n in classe.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "verifier_prediction_rejetee"
    ]

    if len(tests) >= 55 and len(auxiliaires) == 1:
        source = candidat
        reference = commit
        break

if source is None:
    raise SystemExit(
        "Aucune version complete avec 55 tests "
        "retrouvee. Aucun fichier modifie."
    )

arbre = ast.parse(source)
classe = next(
    n for n in arbre.body
    if isinstance(n, ast.ClassDef)
    and n.name == "TestsSecuriteX1000"
)

methode = next(
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name == "verifier_prediction_rejetee"
)

lignes = source.splitlines(keepends=True)

indent = " " * methode.col_offset

nouvelle_methode = f'''{indent}def verifier_prediction_rejetee(
{indent}    self,
{indent}    moteur,
{indent}    positions,
{indent}    actifs=Ellipsis,
{indent}):
{indent}    """Rejet des predictions invalides."""
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
] = [nouvelle_methode]

contenu = "".join(lignes)
ast.parse(contenu, filename=str(fichier))

# Ecriture limitee au fichier de tests.
fichier.write_text(contenu, encoding="utf-8")

print("Version restauree :", reference[:12])
print("Correction actifs=None : appliquee")
print("Syntaxe Python : OK")
print("Aucun autre fichier modifie par ce script")
PY

echo
echo "=== VERIFICATION ==="

python3 -B test_validation_moteurs.py
python3 -B test_coordination_x1000.py

echo
echo "=== FICHIERS MODIFIES ==="
git status --short
git diff --check

echo
echo "REPARATION LOCALE TERMINEE"
echo "Aucun commit ni push effectue"
echo "Aucune archive modifiee"
