#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 - REPARATION CONTROLEE
# Restaure les 55 tests Python.
# Integre la correction du test 35.
# Aucun commit, push, FIGE ou deploiement.

REPO="x1000-intelligence-hippique-v2"
BRANCH="fix/x1000-v2-reparation-controlee"
FICHIER="test_validation_moteurs.py"

SOURCE="40ee2ef330ce93c9e51ecb3beeeb6b192f96bd56"
CORRECTION="81cb72c0de77f7d9c66d9a2f26126c0cc679e32e"

erreur() {
    printf 'ERREUR : %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null || erreur "Git absent"
command -v python3 >/dev/null || erreur "Python absent"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    erreur "Executer dans le depot Git"

cd "$(git rev-parse --show-toplevel)"

[[ "$(basename "$PWD")" == "$REPO" ]] ||
    erreur "Depot incorrect"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
    erreur "Branche non autorisee"

[[ -z "$(git status --porcelain)" ]] ||
    erreur "Depot non propre : annulation"

git cat-file -e "${SOURCE}:${FICHIER}" ||
    erreur "Source historique absente"

git cat-file -e "${CORRECTION}:${FICHIER}" ||
    erreur "Correctif historique absent"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

git show "${SOURCE}:${FICHIER}" > "$TEMP/source.py"
git show "${CORRECTION}:${FICHIER}" > "$TEMP/correctif.py"

python3 -B - "$TEMP" <<'PY'
import ast
import sys
import textwrap
from pathlib import Path

temp = Path(sys.argv[1])
source = (temp / "source.py").read_text(
    encoding="utf-8-sig"
)
correctif = (temp / "correctif.py").read_text(
    encoding="utf-8-sig"
)

arbre = ast.parse(source)
nom_classe = "TestsSecuriteX1000"
nom_methode = "verifier_prediction_rejetee"

classes = [
    n for n in arbre.body
    if isinstance(n, ast.ClassDef)
    and n.name == nom_classe
]

if len(classes) != 1:
    raise SystemExit("Classe de tests invalide")

classe = classes[0]

methodes = [
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(methodes) != 1:
    raise SystemExit("Methode historique absente")

ancienne = methodes[0]

normalise = textwrap.dedent(correctif)
arbre_correctif = ast.parse(normalise)

nouvelles = [
    n for n in arbre_correctif.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(nouvelles) != 1:
    raise SystemExit("Correctif invalide")

nouvelle = nouvelles[0]

lignes = source.splitlines(keepends=True)
lignes_correctif = normalise.splitlines(
    keepends=True
)

bloc = lignes_correctif[
    nouvelle.lineno - 1:nouvelle.end_lineno
]

indentation = " " * ancienne.col_offset

bloc = [
    indentation + ligne if ligne.strip() else ligne
    for ligne in bloc
]

lignes[
    ancienne.lineno - 1:ancienne.end_lineno
] = bloc

resultat = "".join(lignes)
final = ast.parse(resultat)

classes_finales = [
    n for n in final.body
    if isinstance(n, ast.ClassDef)
    and n.name == nom_classe
]

if len(classes_finales) != 1:
    raise SystemExit("Classe finale invalide")

tests = [
    n for n in classes_finales[0].body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(tests) != 55:
    raise SystemExit(
        f"55 tests attendus, {len(tests)} trouves"
    )

methodes_finales = [
    n for n in classes_finales[0].body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(methodes_finales) != 1:
    raise SystemExit("Methode corrigee absente")

methode = methodes_finales[0]
arguments = methode.args.args

if not any(p.arg == "actifs" for p in arguments):
    raise SystemExit("Argument actifs absent")

if not any(
    isinstance(n, ast.Constant)
    and n.value is Ellipsis
    for n in methode.args.defaults
):
    raise SystemExit("Correction Ellipsis absente")

(temp / "restaure.py").write_text(
    resultat,
    encoding="utf-8"
)

print("Syntaxe Python : OK")
print("55 tests : presents")
print("Correction test 35 : integree")
PY

echo "Verification des 55 tests..."

# Les tests s'executent sur une copie temporaire.
mkdir -p "$TEMP/depot"

git archive HEAD | tar -x -C "$TEMP/depot"

cp "$TEMP/restaure.py" \
   "$TEMP/depot/$FICHIER"

(
    cd "$TEMP/depot"
    python3 -B "$FICHIER"
) || erreur "Tests echoues : depot inchange"

[[ -z "$(git status --porcelain)" ]] ||
    erreur "Depot modifie entre-temps"

# Application apres verification.
cp "$TEMP/restaure.py" "$FICHIER"

git diff --check ||
    erreur "Erreur dans le diff"

[[ "$(git diff --name-only)" == "$FICHIER" ]] ||
    erreur "Modification inattendue"

echo
echo "==================================="
echo "X1000 V2.5 - REPARATION TERMINEE"
echo "==================================="
echo "Fichier Python restaure"
echo "Correction du test 35 integree"
echo "55 tests presents"
echo "Tests executes sur copie isolee"
echo "Aucun commit ni push"
echo "Aucun FIGE ni archive modifies"
echo
git status --short
