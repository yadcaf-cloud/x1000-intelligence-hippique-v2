set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
DEPOT="x1000-intelligence-hippique-v2"
SOURCE="tests/test_audit_contrats_x1000.py"
DEST="scripts/audit_contrats_x1000.sh"

echo "=== X1000 PHOENIX V2.4 ==="
echo "=== REPARATION CONTROLEE ==="

# 1. Verifier le depot et la branche
test "$(basename "$(git rev-parse --show-toplevel)")" = "$DEPOT"
test "$(git branch --show-current)" = "$BRANCHE"

# 2. Verifier les fichiers et l'etat Git
test -f "$SOURCE"
test ! -e "$DEST"
test -z "$(git status --porcelain -- "$SOURCE" "$DEST")"

# 3. Verifier le contenu avant modification
python - "$SOURCE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
source = p.read_text(encoding="utf-8-sig")
lines = source.splitlines()

if not lines:
    raise SystemExit("ERREUR : fichier vide")

if lines[0] not in (
    "#!/usr/bin/env bash",
    "set -euo pipefail",
):
    raise SystemExit("ERREUR : contenu inattendu")

if "set -euo pipefail" not in source:
    raise SystemExit("ERREUR : script Bash non confirme")

print("OK : contenu Bash confirme")
PY

# 4. Verifier la syntaxe Bash
bash -n "$SOURCE"
echo "OK : syntaxe Bash"

# 5. Rechercher les references au fichier
echo "=== CONTROLE DES DEPENDANCES ==="

if git grep -n -F "$SOURCE" -- \
    ':!tests/test_audit_contrats_x1000.py'
then
    echo "ATTENTION : references detectees."
    echo "Aucune modification effectuee."
    exit 1
fi

# 6. Creer une sauvegarde hors du depot
SAUVEGARDE="$(mktemp -d)"
cp "$SOURCE" "$SAUVEGARDE/test_audit_contrats_x1000.py"

echo "Sauvegarde : $SAUVEGARDE"

# 7. Deplacer le script Bash
mkdir -p scripts
mv "$SOURCE" "$DEST"
chmod +x "$DEST"

# 8. Verifier l'integrite du deplacement
cmp "$SAUVEGARDE/test_audit_contrats_x1000.py" "$DEST"
bash -n "$DEST"

echo "OK : script Bash deplace et valide"

# 9. Verifier la syntaxe Python sans execution
python -B - <<'PY'
import ast
from pathlib import Path

fichiers = set()

for dossier in ("moteurs", "tests"):
    if Path(dossier).is_dir():
        fichiers.update(Path(dossier).rglob("*.py"))

for nom in (
    "coordination_x1000.py",
    "integration_x1000.py",
    "validation_moteurs.py",
    "api.py",
):
    if Path(nom).is_file():
        fichiers.add(Path(nom))

if not fichiers:
    raise SystemExit("ERREUR : aucun fichier Python")

for fichier in sorted(fichiers):
    ast.parse(
        fichier.read_text(encoding="utf-8-sig"),
        filename=str(fichier),
    )
    print(f"OK : {fichier}")

print("SYNTAXE PYTHON VALIDEE")
PY

# 10. Afficher les modifications locales
echo "=== ETAT FINAL ==="
git status --short

echo "=== REPARATION LOCALE TERMINEE ==="
echo "Aucun commit"
echo "Aucun push"
echo "Aucun deploiement"
echo "Aucun FIGE"
echo "Archives preservees"
