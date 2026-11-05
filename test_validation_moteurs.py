#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 - REPARATION CONTROLEE
# Restauration du fichier de tests Python.
# Correction de verifier_prediction_rejetee.
# Tests avant toute modification du depot.
# Aucun FIGE, aucune archive, aucun deploiement.

REPO="x1000-intelligence-hippique-v2"
BRANCH="fix/x1000-v2-reparation-controlee"
FICHIER="test_validation_moteurs.py"

SOURCE="40ee2ef330ce93c9e51ecb3beeeb6b192f96bd56"
CORRECTION="81cb72c0de77f7d9c66d9a2f26126c0cc679e32e"

erreur() {
    printf 'ERREUR : %s\n' "$*" >&2
    exit 1
}

info() {
    printf '\n=== %s ===\n' "$*"
}

command -v git >/dev/null ||
    erreur "Git absent"

command -v python3 >/dev/null ||
    erreur "Python absent"

command -v tar >/dev/null ||
    erreur "Tar absent"

git rev-parse --is-inside-work-tree \
    >/dev/null 2>&1 ||
    erreur "Executer depuis un depot Git"

cd "$(git rev-parse --show-toplevel)"

[[ "$(basename "$PWD")" == "$REPO" ]] ||
    erreur "Depot incorrect"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
    erreur "Branche non autorisee"

[[ -z "$(git status --porcelain)" ]] ||
    erreur "Depot non propre"

[[ -z "$(git diff --cached --name-only)" ]] ||
    erreur "Index Git non vide"

git cat-file -e "${SOURCE}:${FICHIER}" ||
    erreur "Version Python historique absente"

git cat-file -e "${CORRECTION}:${FICHIER}" ||
    erreur "Correction historique absente"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export TZ=Europe/Paris

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

info "1 - Recuperation des versions"

git show "${SOURCE}:${FICHIER}" \
    > "$TEMP/source.py"

git show "${CORRECTION}:${FICHIER}" \
    > "$TEMP/correction.py"

info "2 - Reconstruction Python securisee"

python3 -B - "$TEMP" <<'PY'
import ast
import sys
import textwrap
from pathlib import Path

temp = Path(sys.argv[1])

source = (temp / "source.py").read_text(
    encoding="utf-8-sig"
)

correction = (temp / "correction.py").read_text(
    encoding="utf-8-sig"
)

arbre = ast.parse(source)
arbre_correctif = ast.parse(correction)

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
        "Methode historique introuvable"
    )

# Le correctif peut etre fourni avec
# une indentation de classe.
correctif_normalise = textwrap.dedent(
    correction
)

arbre_nouveau = ast.parse(
    correctif_normalise
)

nouvelles = [
    n for n in arbre_nouveau.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(nouvelles) != 1:
    raise SystemExit(
        "Correction historique invalide"
    )

ancienne = methodes[0]
nouvelle = nouvelles[0]

lignes_source = source.splitlines(
    keepends=True
)

lignes_nouvelles = (
    correctif_normalise.splitlines(
        keepends=True
    )
)

bloc = lignes_nouvelles[
    nouvelle.lineno - 1:
    nouvelle.end_lineno
]

indentation = " " * ancienne.col_offset

bloc = [
    indentation + ligne
    if ligne.strip()
    else ligne
    for ligne in bloc
]

# Remplacement de la seule methode visee.
lignes_source[
    ancienne.lineno - 1:
    ancienne.end_lineno
] = bloc

resultat = "".join(lignes_source)

final = ast.parse(
    resultat,
    filename="test_validation_moteurs.py"
)

classes_finales = [
    n for n in final.body
    if isinstance(n, ast.ClassDef)
    and n.name == nom_classe
]

if len(classes_finales) != 1:
    raise SystemExit(
        "Classe finale invalide"
    )

classe_finale = classes_finales[0]

tests = [
    n for n in classe_finale.body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(tests) != 55:
    raise SystemExit(
        f"55 tests attendus, {len(tests)} trouves"
    )

methodes_finales = [
    n for n in classe_finale.body
    if isinstance(n, ast.FunctionDef)
    and n.name == nom_methode
]

if len(methodes_finales) != 1:
    raise SystemExit(
        "Methode corrigee absente"
    )

methode = methodes_finales[0]

parametres = methode.args.args

if not any(
    p.arg == "actifs"
    for p in parametres
):
    raise SystemExit(
        "Parametre actifs absent"
    )

if not any(
    isinstance(n, ast.Constant)
    and n.value is Ellipsis
    for n in methode.args.defaults
):
    raise SystemExit(
        "Valeur par defaut Ellipsis absente"
    )

sortie = temp / "restaure.py"

sortie.write_text(
    resultat,
    encoding="utf-8"
)

print("Syntaxe Python : OK")
print("Tests conserves : 55")
print("Correction test 35 : integree")
print("Indentation : valide")
PY

info "3 - Preparation des tests isoles"

mkdir -p "$TEMP/depot"

git archive HEAD |
    tar -x -C "$TEMP/depot"

cp "$TEMP/restaure.py" \
   "$TEMP/depot/$FICHIER"

info "4 - Verification de syntaxe"

(
    cd "$TEMP/depot"

    python3 -B - <<'PY'
import ast
from pathlib import Path

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
    "test_validation_moteurs.py",
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
PY
) || erreur "Syntaxe invalide"

info "5 - Execution des tests"

(
    cd "$TEMP/depot"

    python3 -B test_validation_moteurs.py

    python3 -B test_coordination_x1000.py

) || erreur \
    "Tests echoues : aucune modification appliquee"

info "6 - Application controlee"

[[ -z "$(git status --porcelain)" ]] ||
    erreur "Depot modifie pendant les tests"

cp "$TEMP/restaure.py" "$FICHIER"

git diff --check ||
    erreur "Diff invalide"

MODIFIES="$(git diff --name-only)"

[[ "$MODIFIES" == "$FICHIER" ]] ||
    erreur "Modification inattendue"

info "7 - Verification finale"

python3 -B - "$FICHIER" <<'PY'
import ast
import sys
from pathlib import Path

chemin = Path(sys.argv[1])

ast.parse(
    chemin.read_text(encoding="utf-8"),
    filename=str(chemin),
)

print("Fichier Python final : OK")
PY

git diff --stat
git status --short

echo
echo "Tests locaux termines."
echo "Seul le fichier autorise a ete modifie."
echo
echo "Enregistrer et pousser sur la branche ?"
echo "Tapez OUI pour confirmer :"

read -r CONFIRMATION

if [[ "$CONFIRMATION" != "OUI" ]]; then
    echo "Aucun commit ni push effectue."
    echo "Correction locale conservee."
    exit 0
fi

info "8 - Enregistrement Git"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
    erreur "Branche modifiee"

[[ "$(git diff --name-only)" == "$FICHIER" ]] ||
    erreur "Fichiers modifies inattendus"

git add -- "$FICHIER"

git diff --cached --check ||
    erreur "Index invalide"

[[ "$(git diff --cached --name-only)" == "$FICHIER" ]] ||
    erreur "Index inattendu"

git commit -m \
    "fix(x1000): restore Python validation tests and test 35"

info "9 - Push de la branche"

git push origin \
    "HEAD:refs/heads/$BRANCH"

echo
echo "======================================"
echo "X1000 V2.5 - REPARATION ENREGISTREE"
echo "======================================"
echo "Fichier : $FICHIER"
echo "Branche : $BRANCH"
echo "Syntaxe : verifiee"
echo "Tests locaux : executes"
echo "Correction test 35 : integree"
echo "55 tests : conserves"
echo "Aucun FIGE cree"
echo "Aucune archive modifiee"
echo "Aucun deploiement demande"
echo
echo "Verifier maintenant GitHub Actions."
