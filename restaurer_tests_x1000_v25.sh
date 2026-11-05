#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 V2.5 — Restauration contrôlée
# Aucun commit, push, déploiement ou FIGÉ.
# Aucune modification volontaire des archives.

BRANCH="fix/x1000-v2-reparation-controlee"
SOURCE="40ee2ef330ce93c9e51ecb3beeeb6b192f96bd56"
CORRECTION="81cb72c0de77f7d9c66d9a2f26126c0cc679e32e"
FICHIER="test_validation_moteurs.py"

erreur() {
  echo "ERREUR : $*" >&2
  exit 1
}

command -v git >/dev/null || erreur "Git absent"
command -v python3 >/dev/null || erreur "Python absent"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
  erreur "Exécuter dans un dépôt Git"

cd "$(git rev-parse --show-toplevel)"

[[ "$(basename "$PWD")" == \
  "x1000-intelligence-hippique-v2" ]] ||
  erreur "Dépôt incorrect"

[[ "$(git branch --show-current)" == "$BRANCH" ]] ||
  erreur "Branche non autorisée"

[[ -z "$(git status --porcelain)" ]] ||
  erreur "Dépôt non propre : annulation"

[[ -f "$FICHIER" ]] ||
  erreur "Fichier cible absent"

git cat-file -e "${SOURCE}:${FICHIER}" ||
  erreur "Version historique introuvable"

git cat-file -e "${CORRECTION}:${FICHIER}" ||
  erreur "Correction historique introuvable"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

echo "=== RESTAURATION X1000 V2.5 ==="

python3 -B - <<'PY'
import ast
import os
import subprocess
import tempfile
from pathlib import Path

fichier = Path("test_validation_moteurs.py")
source_ref = "40ee2ef330ce93c9e51ecb3beeeb6b192f96bd56"
correctif_ref = "81cb72c0de77f7d9c66d9a2f26126c0cc679e32e"

def git_show(ref):
    return subprocess.run(
        ["git", "show", f"{ref}:{fichier}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout

def trouver_classe(arbre):
    classes = [
        n for n in arbre.body
        if isinstance(n, ast.ClassDef)
        and n.name == "TestsSecuriteX1000"
    ]
    if len(classes) != 1:
        raise RuntimeError(
            "Classe TestsSecuriteX1000 invalide"
        )
    return classes[0]

def trouver_methode(classe):
    methodes = [
        n for n in classe.body
        if isinstance(n, ast.FunctionDef)
        and n.name == "verifier_prediction_rejetee"
    ]
    if len(methodes) != 1:
        raise RuntimeError(
            "Méthode de validation introuvable"
        )
    return methodes[0]

# 1. Récupération des versions historiques
source = git_show(source_ref)
correctif = git_show(correctif_ref)

arbre = ast.parse(source)
classe = trouver_classe(arbre)
methode = trouver_methode(classe)

tests = [
    n for n in classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(tests) != 55:
    raise RuntimeError(
        f"55 tests attendus, {len(tests)} trouvés"
    )

# 2. Validation de la méthode historique
# Le commit correctif contient une méthode
# isolée : elle est analysée après dédentage.
import textwrap

correctif_nettoye = textwrap.dedent(correctif)
arbre_correctif = ast.parse(correctif_nettoye)

methodes = [
    n for n in arbre_correctif.body
    if isinstance(n, ast.FunctionDef)
    and n.name == "verifier_prediction_rejetee"
]

if len(methodes) != 1:
    raise RuntimeError(
        "Correction historique invalide"
    )

m = methodes[0]

if len(arbre_correctif.body) != 1:
    raise RuntimeError(
        "La correction contient du code inattendu"
    )

if not any(
    isinstance(n, ast.Constant)
    and n.value is Ellipsis
    for n in ast.walk(m)
):
    raise RuntimeError(
        "Gestion Ellipsis absente du correctif"
    )

# 3. Remplacement de la méthode uniquement
lignes = source.splitlines(keepends=True)
indentation = " " * methode.col_offset

nouvelle_methode = textwrap.indent(
    correctif_nettoye.rstrip("\n"),
    indentation,
) + "\n"

lignes[
    methode.lineno - 1:methode.end_lineno
] = [nouvelle_methode]

contenu = "".join(lignes)

# 4. Vérification avant toute écriture
nouvel_arbre = ast.parse(
    contenu,
    filename=str(fichier),
)

nouvelle_classe = trouver_classe(nouvel_arbre)
trouver_methode(nouvelle_classe)

nouveaux_tests = [
    n for n in nouvelle_classe.body
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith("test_")
]

if len(nouveaux_tests) != 55:
    raise RuntimeError(
        "Le nombre de tests a changé"
    )

# 5. Écriture atomique du seul fichier cible
# Le dépôt a déjà été vérifié propre par Bash.
temporaire = None

try:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=str(fichier.parent),
        prefix=".x1000_restauration_",
        suffix=".tmp",
        delete=False,
    ) as sortie:
        temporaire = Path(sortie.name)
        sortie.write(contenu)

    os.chmod(
        temporaire,
        fichier.stat().st_mode & 0o777,
    )
    os.replace(temporaire, fichier)
    temporaire = None

finally:
    if temporaire is not None:
        temporaire.unlink(missing_ok=True)

print("Version Python restaurée :", source_ref[:12])
print("Correction appliquée :", correctif_ref[:12])
print("Nombre de tests :", len(nouveaux_tests))
print("Syntaxe Python : OK")
print("Fichier modifié :", fichier)

PY

echo
echo "=== CONTRÔLE FINAL ==="

python3 -B - <<'PY'
import ast
from pathlib import Path

fichier = Path("test_validation_moteurs.py")
ast.parse(
    fichier.read_text(encoding="utf-8-sig"),
    filename=str(fichier),
)
print("Syntaxe finale : OK")
PY

git diff --check ||
  erreur "Erreur détectée dans le diff"

echo
echo "=== FICHIERS MODIFIÉS ==="
git status --short

MODIFICATIONS="$(git diff --name-only)"
ATTENDU="test_validation_moteurs.py"

[[ "$MODIFICATIONS" == "$ATTENDU" ]] ||
  erreur "Modifications inattendues détectées"

[[ -z "$(git ls-files --others --exclude-standard)" ]] ||
  erreur "Fichiers non suivis détectés"

echo
echo "=== RÉSULTAT ==="
echo "Restauration locale terminée."
echo "55 méthodes de test préservées."
echo "Aucun moteur modifié."
echo "Aucune archive modifiée."
echo "Aucun commit."
echo "Aucun push."
echo "Aucun déploiement."
echo "Aucun FIGÉ."
echo
echo "Le fichier est prêt pour les tests contrôlés."
