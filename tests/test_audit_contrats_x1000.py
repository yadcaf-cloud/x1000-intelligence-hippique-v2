set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
SOURCE="tests/test_audit_contrats_x1000.py"
DEST="scripts/audit_contrats_x1000.sh"

echo "=== X1000 PHOENIX : REPARATION CONTROLEE ==="

test "$(basename "$(git rev-parse --show-toplevel)")" = \
  "x1000-intelligence-hippique-v2"

test "$(git branch --show-current)" = "$BRANCHE"

test -f "$SOURCE"
test ! -e "$DEST"

python - "$SOURCE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
source = p.read_text(encoding="utf-8-sig")
lines = source.splitlines()

if not lines or lines[0] != "#!/usr/bin/env bash":
    raise SystemExit("ERREUR : fichier Bash inattendu")

if "set -euo pipefail" not in source:
    raise SystemExit("ERREUR : contenu inattendu")

print("Script Bash confirme")
PY

bash -n "$SOURCE"

mkdir -p scripts
git mv "$SOURCE" "$DEST"
chmod +x "$DEST"

python - <<'PY'
import ast
from pathlib import Path

files = set()

for folder in ("moteurs", "tests"):
    if Path(folder).is_dir():
        files.update(Path(folder).rglob("*.py"))

for name in (
    "api.py",
    "coordination_x1000.py",
    "integration_x1000.py",
    "validation_moteurs.py",
):
    p = Path(name)
    if p.is_file():
        files.add(p)

errors = []

for p in sorted(files):
    try:
        ast.parse(
            p.read_text(encoding="utf-8-sig"),
            filename=str(p)
        )
        print("OK :", p)
    except (SyntaxError, UnicodeError) as exc:
        errors.append((p, exc))
        print("ERREUR :", p, exc)

if errors:
    raise SystemExit(
        f"{len(errors)} fichier(s) Python invalide(s)"
    )

print("SYNTAXE PYTHON : OK")
PY

bash -n "$DEST"

echo "=== ETAT DES MODIFICATIONS ==="
git status --short

echo "=== REPARATION LOCALE TERMINEE ==="
echo "Aucun commit, push, deploiement ou FIGE."
