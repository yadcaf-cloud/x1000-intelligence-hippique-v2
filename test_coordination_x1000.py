#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 — Réparation contrôlée des tests
# Aucun commit, push, FIGÉ, archive ou publication.

BRANCH="fix/x1000-v2-reparation-controlee"
REPO="x1000-intelligence-hippique-v2"
FICHIER="test_coordination_x1000.py"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export TZ=Europe/Paris

echo "=== X1000 : réparation contrôlée ==="

command -v git >/dev/null || {
  echo "ERREUR : Git absent"
  exit 1
}

command -v python3 >/dev/null || {
  echo "ERREUR : Python absent"
  exit 1
}

cd "$(git rev-parse --show-toplevel)"

test "$(basename "$PWD")" = "$REPO" || {
  echo "ERREUR : dépôt incorrect"
  exit 1
}

test "$(git branch --show-current)" = "$BRANCH" || {
  echo "ERREUR : branche non autorisée"
  exit 1
}

test -z "$(git status --porcelain)" || {
  echo "ERREUR : dépôt non propre"
  exit 1
}

test -f "$FICHIER" && test ! -L "$FICHIER" || {
  echo "ERREUR : fichier absent ou lien symbolique"
  exit 1
}

echo "=== Préparation en copie temporaire ==="

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

git ls-files -z | tar --null -T - -cf - |
  tar -xf - -C "$TEMP"

cd "$TEMP"

python3 -B - <<'PY'
from pathlib import Path
import ast

fichier = Path("test_coordination_x1000.py")
source = fichier.read_text(encoding="utf-8-sig")

ancien = '"id": "TEST-2026-R1-C1",'

nouveau = '''"id": (
            f"{depart_datetime.astimezone(ZoneInfo('Europe/Paris')):%Y-%m-%d}"
            "-R1-C1"
        ),'''

ancien_depart = '''    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    ).isoformat()'''

nouveau_depart = '''    depart_datetime = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    )
    depart = depart_datetime.isoformat()'''

if source.count(ancien) != 1:
    raise SystemExit(
        "ERREUR : identifiant initial introuvable ou ambigu"
    )

if source.count(ancien_depart) != 1:
    raise SystemExit(
        "ERREUR : construction du départ inattendue"
    )

source = source.replace(
    "import unittest\n",
    "import unittest\nfrom zoneinfo import ZoneInfo\n",
    1,
)

source = source.replace(
    ancien_depart,
    nouveau_depart,
    1,
)

source = source.replace(
    ancien,
    nouveau,
    1,
)

ast.parse(source, filename=str(fichier))
fichier.write_text(source, encoding="utf-8")

print("Correction appliquée dans la copie temporaire")
print("Format : AAAA-MM-JJ-R1-C1")
print("Fuseau : Europe/Paris")
PY

echo "=== Tests isolés ==="

python3 -B -m unittest -v \
  test_validation_moteurs \
  test_coordination_x1000

echo "=== SUCCÈS : tests terminés ==="
echo "Dépôt original inchangé"
echo "Aucun commit ni push"
echo "Aucune publication"
echo "Aucun FIGÉ ni archive modifié"
