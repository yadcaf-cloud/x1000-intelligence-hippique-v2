set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
SOURCE="tests/test_audit_contrats_x1000.py"
DEST="scripts/audit_contrats_x1000.sh"

echo "=== X1000 PHOENIX - REPARATION ==="

test "$(basename "$(git rev-parse --show-toplevel)")" = \
  "x1000-intelligence-hippique-v2"

test "$(git branch --show-current)" = "$BRANCHE"
test -f "$SOURCE"
test ! -e "$DEST"

test -z "$(git status --porcelain -- "$SOURCE" "$DEST")"

python - "$SOURCE" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8-sig")

assert s.startswith("set -euo pipefail")
assert 'BRANCHE="fix/x1000-v2-reparation-controlee"' in s
print("OK : script Bash confirme")
PY

bash -n "$SOURCE"

if git grep -n -F "$SOURCE" -- \
  ':!tests/test_audit_contrats_x1000.py'
then
  echo "ERREUR : dependances a examiner"
  exit 1
fi

mkdir -p scripts
mv "$SOURCE" "$DEST"
chmod +x "$DEST"

bash -n "$DEST"

python -B - <<'PY'
import ast
from pathlib import Path

for folder in ("moteurs", "tests"):
    if Path(folder).exists():
        for p in Path(folder).rglob("*.py"):
            ast.parse(
                p.read_text(encoding="utf-8-sig"),
                filename=str(p)
            )

print("OK : syntaxe Python validee")
PY

git status --short

echo "REPARATION LOCALE TERMINEE"
echo "Aucun commit, push, deploiement ou FIGE"
