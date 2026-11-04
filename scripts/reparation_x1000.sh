#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# X1000 — REPARATION CONTROLEE EN COPIE ISOLEE
# Aucun commit, aucun push, aucune modification distante
# Aucune collecte PMU, publication ou creation de FIGE
# ============================================================

SOURCE_COMMIT="fcc9bf3c74"
BRANCHE="fix/x1000-reparation-a-valider"
DATE="$(date -u +%Y%m%dT%H%M%SZ)"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

info() {
  printf '\n[X1000] %s\n' "$*"
}

erreur() {
  printf '\n[ERREUR] %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null || erreur "Git absent"
command -v python3 >/dev/null || erreur "Python 3 absent"

# ------------------------------------------------------------
# 1. VERIFICATION DU DEPOT SOURCE
# ------------------------------------------------------------

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || erreur "Executez ce script depuis le depot Git local X1000."

DEPOT="$(git rev-parse --show-toplevel)"
cd "$DEPOT"

git remote -v

# Ne pas modifier un depot comportant des changements locaux.
# La copie isolee les preserve, mais on les inventorie.
BASE="$(dirname "$DEPOT")"
DOSSIER="$BASE/X1000_REPARATION_$DATE"
COPIE="$DOSSIER/projet"
RAPPORT="$DOSSIER/rapport"

mkdir -p "$RAPPORT"

info "Sauvegarde de l'etat Git"

git rev-parse HEAD > "$RAPPORT/commit_initial.txt"
git branch --show-current > "$RAPPORT/branche_initiale.txt"
git status --porcelain=v1 --untracked-files=all \
  > "$RAPPORT/statut_initial.txt"
git remote -v > "$RAPPORT/remotes.txt"

# Empreintes des fichiers suivis dans le depot source.
python3 - "$DEPOT" "$RAPPORT" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])

paths = subprocess.check_output(
    ["git", "ls-files", "-z"],
    cwd=root
).split(b"\0")

results = {}

for raw in paths:
    if not raw:
        continue

    name = raw.decode("utf-8", "surrogateescape")
    path = root / name

    if path.is_symlink():
        results[name] = {
            "type": "lien_symbolique",
            "cible": str(path.readlink())
        }
        continue

    if not path.is_file():
        results[name] = {"etat": "absent"}
        continue

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024), b""
        ):
            digest.update(block)

    results[name] = {
        "sha256": digest.hexdigest(),
        "taille": path.stat().st_size
    }

(out / "sha256_initial.json").write_text(
    json.dumps(
        results,
        ensure_ascii=False,
        indent=2,
        sort_keys=True
    ),
    encoding="utf-8"
)

print("Fichiers inventories :", len(results))
PY

# ------------------------------------------------------------
# 2. COPIE LOCALE INDEPENDANTE
# ------------------------------------------------------------

info "Creation d'une copie Git isolee"

git clone --no-local --no-checkout \
  "$DEPOT" "$COPIE"

cd "$COPIE"

BASE_COMMIT="$(cat "$RAPPORT/commit_initial.txt")"

git checkout --detach "$BASE_COMMIT"
git switch -c "$BRANCHE"

# Aucun remote dans la copie : empeche un push accidentel.
git remote remove origin

# ------------------------------------------------------------
# 3. RESTAURATION CONTROLEE M1 A M5
# ------------------------------------------------------------

info "Verification du commit historique"

RESTAURATION="NON_EFFECTUEE"

if git cat-file -e "${SOURCE_COMMIT}^{commit}" 2>/dev/null; then

  TEMP="$(mktemp -d)"
  trap 'rm -rf "$TEMP"' EXIT

  OK=1

  for n in 1 2 3 4 5; do

    NOM="m${n}.py"
    CHEMIN="$NOM"

    # Anciennes versions : espace final possible.
    if ! git cat-file -e \
      "${SOURCE_COMMIT}:${CHEMIN}" 2>/dev/null; then

      CHEMIN="${NOM} "

    fi

    if ! git cat-file -e \
      "${SOURCE_COMMIT}:${CHEMIN}" 2>/dev/null; then

      echo "Source historique introuvable : $NOM"
      OK=0
      break
    fi

    git show "${SOURCE_COMMIT}:${CHEMIN}" \
      > "$TEMP/$NOM"

    if ! python3 - "$TEMP/$NOM" <<'PY'
import ast
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text(
    encoding="utf-8-sig"
)
ast.parse(source)
PY
    then
      echo "Syntaxe invalide : $NOM"
      OK=0
      break
    fi

  done

  if [ "$OK" -eq 1 ]; then

    # Aucun moteur existant n'est ecrase.
    for n in 1 2 3 4 5; do
      NOM="m${n}.py"

      if [ -e "$NOM" ]; then
        echo "Moteur deja present : $NOM"
        OK=0
      fi
    done

  fi

  if [ "$OK" -eq 1 ]; then

    for n in 1 2 3 4 5; do
      cp "$TEMP/m${n}.py" "m${n}.py"
    done

    RESTAURATION="PREPAREE"
    info "Cinq moteurs historiques restaures"

  else
    info "Restauration suspendue : verification requise"
  fi

else
  info "Commit historique absent de la copie locale"
  info "Aucun moteur de remplacement invente"
fi

printf '%s\n' "$RESTAURATION" \
  > "$RAPPORT/restauration_moteurs.txt"

# ------------------------------------------------------------
# 4. CORRECTION DU CONTRAT JSON API / SITE
# ------------------------------------------------------------

info "Correction du tableau de bord"

python3 - <<'PY'
from pathlib import Path

path = Path("index.html")

if not path.is_file():
    raise SystemExit("index.html absent")

source = path.read_text(encoding="utf-8")

old_engines = """  const engines = Array.isArray(status.moteurs)
    ? status.moteurs
    : Array.isArray(status.engines)
      ? status.engines
      : [];"""

new_engines = """  const rawEngines =
    status.moteurs ?? status.engines ?? [];

  const engines = Array.isArray(rawEngines)
    ? rawEngines
    : rawEngines &&
      typeof rawEngines === 'object'
      ? Object.values(rawEngines)
      : [];"""

old_status = """      engine.statut ?? engine.status ?? 'État non renseigné'"""

new_status = """      engine.etat ?? engine.statut ??
      engine.status ?? 'État non renseigné'"""

old_array = """    if (Array.isArray(payload.items)) return payload.items;"""

new_array = """    if (Array.isArray(payload.donnees))
      return payload.donnees;
    if (Array.isArray(payload.items)) return payload.items;"""

patches = [
    (old_engines, new_engines),
    (old_status, new_status),
    (old_array, new_array),
]

for old, new in patches:
    count = source.count(old)

    if count != 1:
        raise SystemExit(
            "Correction suspendue : "
            "structure HTML inattendue"
        )

    source = source.replace(old, new, 1)

path.write_text(source, encoding="utf-8")
print("Contrat JSON corrige dans index.html")
PY

# ------------------------------------------------------------
# 5. TESTS STATIQUES ET CONTRAT API
# ------------------------------------------------------------

info "Verification Python"

python3 - <<'PY'
import ast
from pathlib import Path

files = [
    "api.py",
    "noyau_commun.py",
    "verification_moteurs.py",
]

files += [
    f"m{i}.py"
    for i in range(1, 6)
    if Path(f"m{i}.py").is_file()
]

for filename in files:
    path = Path(filename)

    if not path.is_file():
        print("ABSENT :", filename)
        continue

    ast.parse(
        path.read_text(encoding="utf-8-sig"),
        filename=filename
    )

    print("SYNTAXE OK :", filename)
PY

python3 - <<'PY'
from pathlib import Path

api = Path("api.py").read_text(encoding="utf-8")
html = Path("index.html").read_text(encoding="utf-8")

required_api = [
    '/api/status',
    '/api/courses',
    '/api/selections',
    '/api/figes',
    '/api/audits',
    '/api/diagnostic',
]

for endpoint in required_api:
    assert endpoint in api, endpoint

assert "Object.values(rawEngines)" in html
assert "engine.etat" in html
assert "payload.donnees" in html

print("Contrats statiques API/site : OK")
PY

# Verifier la syntaxe JavaScript si Node.js est installe.
if command -v node >/dev/null 2>&1; then

  python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and not dict(attrs).get("src"):
            self.inside = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)

parser = Scripts()
parser.feed(Path("index.html").read_text(
    encoding="utf-8"
))

Path("x1000_verification_temp.js").write_text(
    "\n".join(parser.parts),
    encoding="utf-8"
)
PY

  node --check x1000_verification_temp.js
  rm -f x1000_verification_temp.js

else
  info "Node.js absent : test de syntaxe JS non execute"
fi

# ------------------------------------------------------------
# 6. CONTROLES FIGES ET ARCHIVES
# ------------------------------------------------------------

info "Verification sans modification des archives"

python3 - <<'PY'
from pathlib import Path
import json

for name in ("figes.json", "audits.json"):
    candidates = [
        Path("data") / name,
        Path(name),
    ]

    for path in candidates:
        if not path.is_file():
            continue

        with path.open(encoding="utf-8") as stream:
            json.load(stream)

        print("JSON valide :", path)

print(
    "Aucun FIGE cree, aucun audit modifie."
)
PY

# ------------------------------------------------------------
# 7. RAPPORT FINAL ET EMPREINTES
# ------------------------------------------------------------

info "Creation du rapport de validation"

python3 - "$RAPPORT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
results = {}

for path in Path(".").rglob("*"):
    if not path.is_file():
        continue

    if ".git" in path.parts:
        continue

    results[str(path)] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

(out / "sha256_copie_corrigee.json").write_text(
    json.dumps(
        results,
        indent=2,
        ensure_ascii=False,
        sort_keys=True
    ),
    encoding="utf-8"
)
PY

git status --short > "$RAPPORT/modifications_proposees.txt"
git diff -- index.html > "$RAPPORT/correction_site.diff"

cat > "$RAPPORT/VALIDATION_REQUISE.txt" <<EOF
X1000 - REPARATION CONTROLEE

Commit original :
$BASE_COMMIT

Branche locale :
$BRANCHE

Restauration M1-M5 :
$RESTAURATION

Corrections :
- Contrat JSON API/site
- Verification statique Python
- Verification syntaxe JS si Node.js disponible
- Verification de lecture JSON des archives
- Inventaire SHA-256 avant/apres

LIMITES :
- Tests navigateur ordinateur/mobile non executes
- Autonomie sportive M1-M5 non certifiee
- Regles metier FIGE non certifiees
- Aucune validation officielle automatique
- Aucun commit
- Aucun push
- Aucune modification GitHub

STATUT : EN ATTENTE DE VALIDATION
EOF

info "REPARATION LOCALE PREPAREE"
printf '\nDossier : %s\n' "$DOSSIER"
printf 'Rapport : %s\n' "$RAPPORT"
printf 'Branche locale : %s\n' "$BRANCHE"

echo
echo "AUCUN COMMIT - AUCUN PUSH - AUCUNE PUBLICATION"
echo "VALIDATION HUMAINE OBLIGATOIRE"
