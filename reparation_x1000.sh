#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 PHOENIX V2 — CONTROLE SECURISE
# reparation_x1000.sh
# AUCUNE MODIFICATION / AUCUN DEPLOIEMENT

BRANCH="fix/x1000-v2-reparation-controlee"
SCRIPT="reparation_x1000.sh"

echo "======================================"
echo " X1000 PHOENIX - CONTROLE REPARATION"
echo "======================================"

# 1. Verification du depot
git rev-parse --is-inside-work-tree >/dev/null \
  || { echo "ERREUR : hors depot Git"; exit 1; }

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ "$(basename "$ROOT")" != \
  "x1000-intelligence-hippique-v2" ]]; then
  echo "ERREUR : depot incorrect"
  exit 1
fi

CURRENT="$(git branch --show-current)"

if [[ "$CURRENT" != "$BRANCH" ]]; then
  echo "ERREUR : branche incorrecte : $CURRENT"
  exit 1
fi

# 2. Protection des fichiers
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  echo "ERREUR : depot non propre"
  echo "Aucune modification effectuee"
  exit 1
fi

# 3. Verification du script
if [[ ! -f "$SCRIPT" || -L "$SCRIPT" ]]; then
  echo "ERREUR : script absent ou lien symbolique"
  exit 1
fi

echo "Verification syntaxique Bash..."
bash -n "$SCRIPT"

echo "SYNTAXE BASH : OK"

# 4. Verification des composants attendus
python3 -B - <<'PY'
from pathlib import Path
import ast

script = Path("reparation_x1000.sh")
content = script.read_text(encoding="utf-8-sig")

required = [
    "set -Eeuo pipefail",
    "api.py",
    "render.yaml",
    "tests_historiques",
    "moteurs/m1.py",
    "moteurs/m2.py",
    "moteurs/m3.py",
    "moteurs/m4.py",
    "moteurs/m5.py",
]

missing = [item for item in required if item not in content]

if missing:
    raise SystemExit(
        "ERREUR : elements manquants : " + ", ".join(missing)
    )

for name in ["api.py"] + [
    f"moteurs/m{i}.py" for i in range(1, 6)
]:
    path = Path(name)
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"ERREUR : fichier absent : {name}")

    ast.parse(
        path.read_text(encoding="utf-8-sig"),
        filename=name
    )
    print("SYNTAXE OK :", name)

print("STRUCTURE DU SCRIPT : OK")
PY

# 5. Verification de la reference PHOENIX
echo "Controle des references PHOENIX..."

if grep -qi "PHOENIX" "$SCRIPT"; then
  echo "INFO : reference PHOENIX presente"
  echo "Cette reference n'est pas une erreur."
else
  echo "INFO : aucune reference PHOENIX"
fi

# 6. Verification de non-modification
git diff --exit-code HEAD --
git diff --cached --exit-code HEAD --

if [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
  echo "ERREUR : nouveaux fichiers detectes"
  exit 1
fi

echo "======================================"
echo " CONTROLE X1000 TERMINE"
echo "======================================"
echo "Syntaxe : OK"
echo "Structure : OK"
echo "M1-M5 : syntaxe verifiee"
echo "FIGES : non modifies"
echo "Archives : non modifiees"
echo "Pronostics : non modifies"
echo "Aucun commit"
echo "Aucun push"
echo "Aucun deploiement"
echo "Aucune publication"
echo "======================================"
