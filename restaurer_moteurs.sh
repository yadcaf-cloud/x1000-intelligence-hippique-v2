#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# X1000 V2 — RESTAURATION CONTROLEE M1 A M5
#
# Objectif :
# - Restaurer les contenus du commit source
# - Supprimer uniquement les espaces finaux
#   des noms M1, M2 et M3
# - Verifier l'integrite des cinq fichiers
# - Verifier leur syntaxe Python
# - Ne faire aucun commit ni push
#
# Executer depuis la racine du depot.
# ============================================================

SOURCE="fcc9bf3c74"
BRANCHE="fix/restauration-m1-m5"

erreur() {
    echo "ERREUR : $*" >&2
    exit 1
}

info() {
    echo
    echo ">>> $*"
}

# ============================================================
# 1. VERIFIER LE DEPOT
# ============================================================

git rev-parse --is-inside-work-tree \
    >/dev/null 2>&1 \
    || erreur "Ce dossier n'est pas un depot Git."

RACINE="$(git rev-parse --show-toplevel)"

cd "$RACINE"

[ -z "$(git status --porcelain --untracked-files=all)" ] \
    || erreur "Modifications locales presentes."

git remote get-url origin >/dev/null 2>&1 \
    || erreur "Remote origin introuvable."

# ============================================================
# 2. VERIFIER LA BRANCHE CIBLE
# ============================================================

if git show-ref --verify --quiet \
    "refs/heads/$BRANCHE"; then
    erreur "La branche locale existe deja : $BRANCHE"
fi

# ============================================================
# 3. ACTUALISER MAIN
# ============================================================

info "Actualisation de main"

git fetch origin main

git switch main

git merge --ff-only origin/main \
    || erreur "main ne peut pas etre actualisee en fast-forward."

# ============================================================
# 4. VERIFIER LE COMMIT SOURCE
# ============================================================

info "Verification du commit source"

git cat-file -e "${SOURCE}^{commit}" \
    || erreur "Commit source introuvable."

SOURCE_COMPLET="$(
    git rev-parse "${SOURCE}^{commit}"
)"

echo "Commit source : $SOURCE_COMPLET"

# ============================================================
# 5. VERIFIER LES CINQ FICHIERS ORIGINAUX
# ============================================================

ORIGINAUX=(
    "m1.py "
    "m2.py "
    "m3.py "
    "m4.py"
    "m5.py"
)

CIBLES=(
    "m1.py"
    "m2.py"
    "m3.py"
    "m4.py"
    "m5.py"
)

for index in "${!ORIGINAUX[@]}"; do

    original="${ORIGINAUX[$index]}"
    cible="${CIBLES[$index]}"

    git cat-file -e \
        "${SOURCE_COMPLET}:${original}" \
        || erreur "Original absent : [$original]"

    # Ne jamais remplacer un fichier cible existant.
    if [ -e "$cible" ] || [ -L "$cible" ]; then
        erreur "Fichier cible deja present : $cible"
    fi

    # Ne pas ecraser non plus un chemin original
    # deja present dans la branche main.
    if [ -e "$original" ] || [ -L "$original" ]; then
        erreur "Chemin original deja present : [$original]"
    fi

    echo "Original verifie : [$original]"

done

# ============================================================
# 6. CREER LA BRANCHE DE RESTAURATION
# ============================================================

info "Creation de la branche"

git switch -c "$BRANCHE"

# ============================================================
# 7. RESTAURER LES FICHIERS ORIGINAUX
# ============================================================

info "Restauration des cinq moteurs"

git restore \
    --source="$SOURCE_COMPLET" \
    --staged \
    --worktree \
    -- "${ORIGINAUX[@]}"

# ============================================================
# 8. CORRIGER UNIQUEMENT LES NOMS
# ============================================================

info "Correction des noms M1, M2 et M3"

git mv -- "m1.py " "m1.py"
git mv -- "m2.py " "m2.py"
git mv -- "m3.py " "m3.py"

# M4 et M5 possedent deja les noms attendus.

# ============================================================
# 9. VERIFIER L'INTEGRITE DES CONTENUS
# ============================================================

info "Verification des empreintes Git"

for index in "${!ORIGINAUX[@]}"; do

    original="${ORIGINAUX[$index]}"
    cible="${CIBLES[$index]}"
    numero=$((index + 1))

    attendu="$(
        git rev-parse "${SOURCE_COMPLET}:${original}"
    )"

    actuel="$(
        git hash-object -- "$cible"
    )"

    if [ "$attendu" != "$actuel" ]; then
        erreur "Contenu M${numero} modifie."
    fi

    echo "M${numero} : contenu original preserve."

done

# ============================================================
# 10. VERIFIER LA SYNTAXE PYTHON
# ============================================================

info "Verification syntaxique"

python - <<'PY'
import ast
from pathlib import Path

for numero in range(1, 6):
    chemin = Path(f"m{numero}.py")

    contenu = chemin.read_text(
        encoding="utf-8-sig"
    )

    ast.parse(
        contenu,
        filename=str(chemin),
    )

    print(
        f"M{numero} : syntaxe Python valide"
    )
PY

# ============================================================
# 11. VERIFIER LES FICHIERS ATTENDUS
# ============================================================

info "Controle des noms"

for numero in 1 2 3 4 5; do

    test -f "m${numero}.py" \
        || erreur "M${numero} absent."

done

for numero in 1 2 3; do

    test ! -e "m${numero}.py " \
        || erreur "Ancien nom M${numero} present."

done

# ============================================================
# 12. AFFICHER LES MODIFICATIONS
# ============================================================

info "Etat du depot"

git status --short

info "Resume des modifications indexees"

git diff --cached --stat

info "Resume des modifications non indexees"

git diff --stat

info "Verification des espaces dans le diff"

git diff --cached --check
git diff --check

# ============================================================
# 13. FIN
# ============================================================

echo
echo "============================================"
echo "X1000 V2 — RESTAURATION PREPAREE"
echo "============================================"
echo "Branche : $BRANCHE"
echo "Source  : $SOURCE_COMPLET"
echo
echo "M1 : restaure et nom corrige"
echo "M2 : restaure et nom corrige"
echo "M3 : restaure et nom corrige"
echo "M4 : restaure"
echo "M5 : restaure"
echo
echo "Contenus : empreintes verifiees"
echo "Syntaxe  : verification effectuee"
echo
echo "AUCUN COMMIT EFFECTUE"
echo "AUCUN PUSH EFFECTUE"
echo "============================================"
