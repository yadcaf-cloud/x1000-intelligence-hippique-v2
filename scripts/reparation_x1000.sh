#!/usr/bin/env bash
set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
SOURCE=".github/workflows/dashboard_x1000.html"

echo "=== X1000 : REPARATION CONTROLEE ==="

git rev-parse --show-toplevel >/dev/null
cd "$(git rev-parse --show-toplevel)"

if [[ "$(git branch --show-current)" != "$BRANCHE" ]]; then
  echo "ERREUR : branche incorrecte"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERREUR : depot non propre"
  exit 1
fi

if [[ ! -s "$SOURCE" ]]; then
  echo "ERREUR : tableau de bord source absent"
  exit 1
fi

for fichier in index.html pmu.html; do
  if [[ -e "$fichier" ]]; then
    echo "ERREUR : $fichier existe deja"
    exit 1
  fi
done

python3 - <<'PY'
from pathlib import Path
from html.parser import HTMLParser

source = Path(".github/workflows/dashboard_x1000.html")
contenu = source.read_text(encoding="utf-8-sig")

class Controle(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)

p = Controle()
p.feed(contenu)
p.close()

for tag in ("html", "head", "body"):
    if tag not in p.tags:
        raise SystemExit(f"ERREUR : balise {tag} absente")

if not contenu.strip().lower().endswith("</html>"):
    raise SystemExit("ERREUR : fermeture HTML absente")

for nom in ("index.html", "pmu.html"):
    cible = Path(nom)
    with cible.open("x", encoding="utf-8") as f:
        f.write(contenu)
    print("PAGE CREEE :", cible)

print("CONTROLE HTML INITIAL : OK")
PY

git add -- index.html pmu.html

if [[ "$(git diff --cached --name-only)" != $'index.html\npmu.html' ]]; then
  echo "ERREUR : modifications inattendues"
  git reset -- index.html pmu.html
  exit 1
fi

git diff --cached --check
git diff --cached --stat

echo "=== VALIDATION ==="
echo "Seuls index.html et pmu.html sont prepares."
echo "Aucun FIGE, pronostic ou moteur modifie."

git commit -m "fix(pages): restaurer pages publiques X1000"
git push origin "$BRANCHE"

echo "=== REPARATION ENVOYEE ==="
  
