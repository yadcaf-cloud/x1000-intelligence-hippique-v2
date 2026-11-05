#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 - REPARATION CONTROLEE
# Restauration Python et correction du test 35.
# Aucun commit, push, deploiement ou FIGE.
# Aucun changement volontaire des archives.

BRANCH="fix/x1000-v2-reparation-controlee"
REPO="x1000-intelligence-hippique-v2"
FICHIER="test_validation_moteurs.py"

SOURCE="40ee2ef330ce93c9e51ecb3beeeb6b192f96bd56"
CORRECTION="81cb72c0de77f7d9c66d9a2f26126c0cc679e32e"

erreur() {
    echo "ERREUR : $*" >&2
    exit 1
}

info() {
    printf '\n=== %s ===\n' "$*"
}

command -v git >/dev/null ||
    erreur "Git absent"

command -v python3 >/dev/null ||
    erreur "Python absent"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    erreur "Executer dans le depot Git"

cd "$(git rev-parse --show-toplevel)"

[[ "$(basename "$PWD")" == "$REPO" ]] ||
    erreur "Depot incorrect"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
    erreur "Branche non autorisee"

[[ -z "$(git status --porcelain)" ]] ||
    erreur "Depot non propre : intervention annulee"

git cat-file -e "${SOURCE}:${FICHIER}" ||
    erreur "Source historique introuvable"

git cat-file -e "${CORRECTION}:${FICHIER}" ||
    erreur "Correction historique introuvable"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export TZ=Europe/Paris

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

info "1 - Restaurer le fichier Python"

git show "${SOURCE}:${FICHIER}" \
    > "$TEMP/source.py"

git show "${CORRECTION}:${FICHIER}" \
    > "$TEMP/correction.py"

python3 -B - "$TEMP" <<'PY'
import ast
import sys
from pathlib import Path

temp = Path(sys.argv[1])
source = (temp / "source.py").read_text(
    encoding="utf-8-sig"
)
correction = (temp / "correction.py").read_text(
    encoding="utf-8-sig"
)

arbre = ast.parse(source)
correctif = ast.parse(correction)

nom_classe = "TestsSecuriteX1000"
nom_methode = "verifier_prediction_rejetee"

classes = [
    n for n in arbre.body
    if isinstance(n, ast.ClassDef)
    and n.name == nom_classe
]

if len(classes) != 1:
    raise SystemExit(
        "Classe de tests absente ou ambigue"
    )

classe = classes[0]

methodes = [
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(methodes) != 1:
    raise SystemExit(
        "Methode de validation introuvable"
    )

candidats = [
    n for n in correctif.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(candidats) != 1:
    raise SystemExit(
        "Correctif historique invalide"
    )

ancienne = methodes[0]
nouvelle = candidats[0]

lignes_source = source.splitlines(
    keepends=True
)
lignes_correctif = correction.splitlines(
    keepends=True
)

bloc = lignes_correctif[
    nouvelle.lineno - 1:nouvelle.end_lineno
]

indentation = " " * ancienne.col_offset

bloc = [
    indentation + ligne
    if ligne.strip()
    else ligne
    for ligne in bloc
]

lignes_source[
    ancienne.lineno - 1:ancienne.end_lineno
] = bloc

resultat = "".join(lignes_source)

arbre_final = ast.parse(
    resultat,
    filename="test_validation_moteurs.py"
)

classes_finales = [
    n for n in arbre_final.body
    if isinstance(n, ast.ClassDef)
    and n.name == nom_classe
]

classe_finale = classes_finales[0]

tests = [
    n for n in classe_finale.body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(tests) < 55:
    raise SystemExit(
        "Suite de tests incomplete : "
        f"{len(tests)} tests"
    )

methodes_finales = [
    n for n in classe_finale.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(methodes_finales) != 1:
    raise SystemExit(
        "Correction de methode invalide"
    )

(temp / "restaure.py").write_text(
    resultat,
    encoding="utf-8"
)

print("Syntaxe Python : OK")
print("Tests retrouves :", len(tests))
print("Correction test 35 : integree")
PY

info "2 - Verifier la syntaxe M1 a M5"

python3 -B - "$TEMP" <<'PY'
import ast
import sys
from pathlib import Path

temp = Path(sys.argv[1])

fichiers = [
    "m1.py",
    "m2.py",
    "m3.py",
    "m4.py",
    "m5.py",
    "noyau_commun.py",
    "moteurs/noyau_commun.py",
    "validation_moteurs.py",
    "coordination_x1000.py",
    "test_coordination_x1000.py",
]

for nom in fichiers:
    chemin = Path(nom)
    if not chemin.is_file():
        raise SystemExit(
            f"Fichier manquant : {nom}"
        )

    ast.parse(
        chemin.read_text(
            encoding="utf-8-sig"
        ),
        filename=nom,
    )

    print("SYNTAXE OK :", nom)

restaure = temp / "restaure.py"

ast.parse(
    restaure.read_text(encoding="utf-8"),
    filename="test_validation_moteurs.py",
)

print(
    "SYNTAXE OK : test_validation_moteurs.py"
)
PY

info "3 - Preparer les tests isoles"

mkdir -p "$TEMP/depot"

git archive HEAD |
    tar -x -C "$TEMP/depot"

cp "$TEMP/restaure.py" \
   "$TEMP/depot/$FICHIER"

info "4 - Executer les tests"

(
    cd "$TEMP/depot"

    python3 -B test_validation_moteurs.py

    python3 -B test_coordination_x1000.py
) || erreur "Tests echoues : aucune restauration appliquee"

info "5 - Appliquer la restauration"

cp "$TEMP/restaure.py" "$FICHIER"

git diff --check ||
    erreur "Erreur dans le diff"

info "6 - Controle final"

MODIFIES="$(git diff --name-only)"

[[ "$MODIFIES" == "$FICHIER" ]] ||
    erreur "Modification inattendue detectee"

python3 -B - "$FICHIER" <<'PY'
import ast
import sys
from pathlib import Path

chemin = Path(sys.argv[1])

ast.parse(
    chemin.read_text(encoding="utf-8"),
    filename=str(chemin),
)

print("Fichier restaure : syntaxe OK")
PY

git status --short
git diff --stat

echo
echo "===================================="
echo "X1000 V2.5 - REPARATION TERMINEE"
echo "===================================="
echo "M1 a M5 : syntaxe verifiee"
echo "Tests : executes en copie isolee"
echo "Fichier restaure : $FICHIER"
echo "Branche : $BRANCH"
echo "Aucun commit ni push"
echo "Aucun deploiement"
echo "Aucun FIGE automatique"
echo "Archives originales preservees"
echo
echo "ETAPE SUIVANTE :"
echo "Verifier le diff puis enregistrer"
echo "la correction sur la branche."
