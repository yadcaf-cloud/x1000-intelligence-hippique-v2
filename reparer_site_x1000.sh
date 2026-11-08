#!/usr/bin/env bash
set -euo pipefail

BRANCHE="fix/x1000-v2-reparation-controlee"
WORKFLOW=".github/workflows/preparation-operationnelle-x1000.yml"
SOURCE=".github/workflows/dashboard_x1000.html"

echo "=== X1000 - REPARATION CONTROLEE ==="

git rev-parse --show-toplevel >/dev/null

if [[ "$(git branch --show-current)" != "$BRANCHE" ]]; then
  echo "ERREUR : branche incorrecte"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERREUR : modifications locales existantes"
  exit 1
fi

for fichier in "$WORKFLOW" "$SOURCE"; do
  if [[ ! -s "$fichier" ]]; then
    echo "ERREUR : fichier absent : $fichier"
    exit 1
  fi
done

for fichier in index.html pmu.html dashboard_x1000.html; do
  if [[ -e "$fichier" ]]; then
    echo "ERREUR : $fichier existe deja"
    echo "Aucune page existante ne sera ecrasee."
    exit 1
  fi
done

python3 - <<'PY'
from pathlib import Path
from html import escape
from shutil import copy2

root = Path.cwd()
workflow = root / ".github/workflows/preparation-operationnelle-x1000.yml"
source = root / ".github/workflows/dashboard_x1000.html"

original = workflow.read_text(encoding="utf-8")

debut = "      - name: Verifier pages et liens GitHub Pages\n"
fin = "      - name: Controle final\n"

if original.count(debut) != 1 or original.count(fin) != 1:
    raise SystemExit("Structure du workflow inattendue : aucune modification")

start = original.index(debut)
end = original.index(fin, start)

def page(titre, description, contenu):
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#071521">
<meta name="description" content="{escape(description, quote=True)}">
<title>{escape(titre)}</title>
<style>
:root {{
  color-scheme:dark;
  font-family:system-ui,sans-serif;
  background:#071521;
  color:#f0f7f5;
}}
* {{box-sizing:border-box}}
body {{margin:0;line-height:1.6}}
header,footer {{padding:2rem 1rem;text-align:center}}
main {{max-width:1000px;margin:auto;padding:1rem}}
h1,h2 {{color:#efce7e}}
a {{color:#a7dfff}}
nav {{display:flex;flex-wrap:wrap;gap:1rem}}
nav a,section {{
  background:#102838;
  border:1px solid #315263;
  border-radius:12px;
  padding:1.2rem;
}}
section {{margin:1.5rem 0}}
</style>
</head>
<body>
<header><h1>{escape(titre)}</h1></header>
<main>
<nav aria-label="Navigation principale">
<a href="index.html">Accueil</a>
<a href="pmu.html">Courses PMU</a>
<a href="dashboard_x1000.html">Tableau de bord</a>
</nav>
{contenu}
</main>
<footer>X1000 - Consultation statique</footer>
</body>
</html>
"""

accueil = page(
    "X1000 Intelligence Hippique V2",
    "Accueil du projet X1000",
    """<section>
<h2>Intelligence hippique</h2>
<p>Cinq moteurs independants M1, M2, M3, M4 et M5.</p>
<p>Coordination centrale X1000.</p>
<p>Aucune modification automatique des FIGES ou archives.</p>
</section>
<section>
<h2>Navigation</h2>
<p><a href="pmu.html">Consulter l'espace PMU</a></p>
<p><a href="dashboard_x1000.html">Ouvrir le tableau de bord</a></p>
</section>"""
)

pmu = page(
    "X1000 - Courses PMU France",
    "Espace de consultation PMU France",
    """<section>
<h2>Courses PMU en France</h2>
<p>Les analyses necessitent des donnees verifiees.</p>
<p>Aucun pronostic ni resultat officiel n'est invente.</p>
</section>
<section>
<h2>Protections</h2>
<p>Decisions independantes des cinq moteurs.</p>
<p>FIGES et archives preserves.</p>
<p>Cette page statique ne declenche aucune publication.</p>
</section>"""
)

controle = """      - name: Verifier pages et liens GitHub Pages
        shell: bash
        run: |
          python - <<'PYHTML'
          from pathlib import Path
          from html.parser import HTMLParser
          from urllib.parse import urlsplit, unquote

          root = Path.cwd().resolve()
          erreurs = []

          class Scanner(HTMLParser):
              def __init__(self):
                  super().__init__()
                  self.tags = set()
                  self.links = []

              def handle_starttag(self, tag, attrs):
                  self.tags.add(tag)
                  d = dict(attrs)
                  for attr in ("href", "src"):
                      if d.get(attr):
                          self.links.append(d[attr])

          pages = [
              root / "index.html",
              root / "pmu.html",
              root / "dashboard_x1000.html",
          ]

          for page in pages:
              if not page.is_file() or not page.stat().st_size:
                  erreurs.append(f"Page absente ou vide: {page.name}")
                  continue

              html = page.read_text(encoding="utf-8-sig")
              scanner = Scanner()
              scanner.feed(html)
              scanner.close()

              for tag in ("html", "head", "body"):
                  if tag not in scanner.tags:
                      erreurs.append(f"{page.name}: balise {tag} absente")

              if not html.rstrip().lower().endswith("</html>"):
                  erreurs.append(f"{page.name}: fermeture HTML absente")

              for lien in scanner.links:
                  lien = lien.strip()
                  if not lien or lien.startswith("#"):
                      continue

                  u = urlsplit(lien)
                  if u.scheme or u.netloc or not u.path:
                      continue

                  chemin = unquote(u.path)

                  if chemin.startswith("/"):
                      prefix = "/x1000-intelligence-hippique-v2/"
                      if not chemin.startswith(prefix):
                          erreurs.append(f"Chemin absolu invalide: {lien}")
                          continue
                      cible = root / chemin[len(prefix):]
                  else:
                      cible = page.parent / chemin

                  cible = cible.resolve()

                  if not cible.is_relative_to(root):
                      erreurs.append(f"Chemin hors depot: {lien}")
                      continue

                  if cible.is_dir():
                      cible = cible / "index.html"

                  if not cible.is_file():
                      erreurs.append(f"Lien inexistant: {page.name}: {lien}")

              print("HTML controle:", page.name)

          if erreurs:
              for erreur in erreurs:
                  print(f"::error::{erreur}")
              raise SystemExit(1)

          print("Pages publiques : OK")
          print("Liens locaux : OK")
          print("Publication statique : structure valide")
          PYHTML

      - name: Verifier publication GitHub Pages
        shell: bash
        run: |
          set -euo pipefail
          for page in index.html pmu.html dashboard_x1000.html; do
            test -s "$page" || exit 1
          done
          echo "Fichiers HTML presents a la racine"
          echo "Deploiement effectif non verifie"

"""

nouveau = original[:start] + controle + original[end:]

protections = [
    "Tester moteurs M1-M5",
    "Executer tests de regression",
    "Controler six routes API",
    "Controle final",
]

for protection in protections:
    if protection not in nouveau:
        raise SystemExit(f"Protection manquante: {protection}")

copy2(source, root / "dashboard_x1000.html")
(root / "index.html").write_text(accueil, encoding="utf-8")
(root / "pmu.html").write_text(pmu, encoding="utf-8")
workflow.write_text(nouveau, encoding="utf-8")

print("Pages HTML creees")
print("Workflow corrige")
print("Controles M1-M5 et API conserves")
print("Aucun FIGE ni archive modifie")
PY

git add -- \
  index.html \
  pmu.html \
  dashboard_x1000.html \
  "$WORKFLOW"

echo "=== REPARATION PREPAREE ==="
git diff --cached --stat
echo "Verifier les modifications avant commit."
