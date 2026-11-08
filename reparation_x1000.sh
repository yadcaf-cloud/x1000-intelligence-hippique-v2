#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# X1000 V2 — DIAGNOSTIC SECURISE
# API + M1-M5 + COORDINATION + RENDER + TESTS
#
# LECTURE SEULE — AUCUNE REPARATION AUTOMATIQUE
# AUCUN COMMIT / PUSH / DEPLOIEMENT / PUBLICATION
# AUCUNE MODIFICATION DES FIGES OU ARCHIVES
# ==========================================================

BRANCH="fix/x1000-v2-reparation-controlee"
REPO="x1000-intelligence-hippique-v2"
SCRIPT="reparation_x1000.sh"

ERRORS=0
WARNINGS=0
CHECKS=0

ok() {
  printf 'OK : %s\n' "$1"
}

warn() {
  printf 'ATTENTION : %s\n' "$1"
  WARNINGS=$((WARNINGS + 1))
}

fail() {
  printf 'ERREUR : %s\n' "$1"
  ERRORS=$((ERRORS + 1))
}

section() {
  printf '\n========================================\n'
  printf '%s\n' "$1"
  printf '========================================\n'
}

check_file() {
  local path="$1"
  local required="${2:-yes}"

  CHECKS=$((CHECKS + 1))

  if [[ -L "$path" ]]; then
    fail "Lien symbolique interdit : $path"
    return 1
  fi

  if [[ ! -f "$path" ]]; then
    if [[ "$required" == "yes" ]]; then
      fail "Fichier obligatoire absent : $path"
    else
      warn "Fichier optionnel absent : $path"
    fi
    return 1
  fi

  ok "Fichier present : $path"
  return 0
}

check_python() {
  local path="$1"

  if ! check_file "$path" yes; then
    return 0
  fi

  if python3 -B - "$path" <<'PY'
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    source = path.read_text(encoding="utf-8-sig")
    ast.parse(source, filename=str(path))
except (SyntaxError, UnicodeError, OSError) as exc:
    print(f"DETAIL : {exc}", file=sys.stderr)
    sys.exit(1)
PY
  then
    ok "Syntaxe Python : $path"
  else
    fail "Syntaxe Python invalide : $path"
  fi
}

section "X1000 V2 — CONTROLE SECURISE"

# ----------------------------------------------------------
# 1. OUTILS NECESSAIRES
# ----------------------------------------------------------

section "1. OUTILS"

for tool in git bash python3; do
  if command -v "$tool" >/dev/null 2>&1; then
    ok "Outil disponible : $tool"
  else
    printf 'ERREUR FATALE : outil absent : %s\n' "$tool"
    exit 2
  fi
done

# ----------------------------------------------------------
# 2. IDENTITE DU DEPOT
# ----------------------------------------------------------

section "2. DEPOT ET BRANCHE"

if ! git rev-parse --is-inside-work-tree \
  >/dev/null 2>&1; then
  echo "ERREUR FATALE : hors depot Git"
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ "$(basename "$ROOT")" != "$REPO" ]]; then
  echo "ERREUR FATALE : depot incorrect"
  exit 2
fi

ok "Depot : $REPO"

CURRENT="$(git branch --show-current)"

if [[ "$CURRENT" != "$BRANCH" ]]; then
  echo "ERREUR FATALE : branche incorrecte"
  echo "Branche actuelle : $CURRENT"
  echo "Branche attendue : $BRANCH"
  exit 2
fi

ok "Branche autorisee : $CURRENT"

# ----------------------------------------------------------
# 3. PROTECTION DU DEPOT
# ----------------------------------------------------------

section "3. PROTECTION DES DONNEES"

if [[ -n "$(git status --porcelain \
  --untracked-files=all)" ]]; then
  echo "ERREUR FATALE : depot non propre"
  echo "Le diagnostic est interrompu."
  echo "Aucun fichier ne sera modifie."
  exit 2
fi

ok "Depot propre avant controle"

BEFORE_HEAD="$(git rev-parse HEAD)"
BEFORE_TREE="$(git rev-parse HEAD^{tree})"

# ----------------------------------------------------------
# 4. CONTROLE DU SCRIPT BASH
# ----------------------------------------------------------

section "4. SCRIPT DE CONTROLE"

if check_file "$SCRIPT" yes; then
  if bash -n "$SCRIPT"; then
    ok "Syntaxe Bash valide"
  else
    fail "Syntaxe Bash invalide"
  fi
fi

# ----------------------------------------------------------
# 5. MOTEURS INDEPENDANTS M1-M5
# ----------------------------------------------------------

section "5. MOTEURS M1 A M5"

for i in 1 2 3 4 5; do
  check_python "moteurs/m${i}.py"
done

# ----------------------------------------------------------
# 6. API ET COORDINATION
# ----------------------------------------------------------

section "6. API ET COORDINATION"

check_python "api.py"
check_python "coordination_x1000.py"

for path in \
  "integration_x1000.py" \
  "validation_moteurs.py"; do

  if [[ -f "$path" && ! -L "$path" ]]; then
    check_python "$path"
  else
    warn "Composant non trouve : $path"
  fi
done

# ----------------------------------------------------------
# 7. CONFIGURATION RENDER
# ----------------------------------------------------------

section "7. CONFIGURATION RENDER"

if [[ -f "render.yaml" || -L "render.yaml" ]]; then
  RENDER_FILE="render.yaml"
elif [[ -f "render.yml" || -L "render.yml" ]]; then
  RENDER_FILE="render.yml"
else
  RENDER_FILE=""
fi

if [[ -n "$RENDER_FILE" ]]; then
  if [[ -L "$RENDER_FILE" ]]; then
    fail "Lien symbolique Render interdit"
  else
    ok "Configuration Render presente"

    if python3 -B - "$RENDER_FILE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    content = path.read_text(encoding="utf-8-sig")
except (OSError, UnicodeError) as exc:
    sys.exit(f"Lecture Render impossible : {exc}")

if not content.strip():
    sys.exit("Configuration Render vide")

try:
    import yaml
except ImportError:
    print("INFO : PyYAML absent, analyse YAML ignoree")
    sys.exit(3)

try:
    data = yaml.safe_load(content)
except yaml.YAMLError as exc:
    sys.exit(f"Configuration YAML invalide : {exc}")

if not isinstance(data, dict):
    sys.exit("Configuration YAML non structuree")

print("Configuration YAML analysee")
PY
    then
      ok "Controle Render termine"
    else
      rc=$?
      if (( rc == 3 )); then
        warn "Analyse YAML non effectuee : PyYAML absent"
      else
        fail "Configuration Render invalide"
      fi
    fi
  fi
else
  warn "render.yaml ou render.yml absent"
  warn "Configuration externe Render non verifiee"
fi

# ----------------------------------------------------------
# 8. TESTS HISTORIQUES
# ----------------------------------------------------------

section "8. TESTS HISTORIQUES"

if [[ -L "tests_historiques" || -L "tests" ]]; then
  fail "Lien symbolique sur dossier de tests"
elif [[ -d "tests_historiques" ]]; then

  ok "Dossier tests_historiques present"

  while IFS= read -r -d '' path; do
    check_python "$path"
  done < <(
    find tests_historiques \
      -type f -name '*.py' -print0
  )

elif [[ -d "tests" ]]; then

  ok "Dossier tests present"

  while IFS= read -r -d '' path; do
    check_python "$path"
  done < <(
    find tests \
      -type f -name '*.py' -print0
  )

else
  warn "Aucun dossier de tests reconnu"
fi

# ----------------------------------------------------------
# 9. IDENTITE X1000 V2
# ----------------------------------------------------------

section "9. IDENTITE X1000 V2"

if grep -qi "X1000 V2" "$SCRIPT"; then
  ok "Reference X1000 V2 presente"
else
  warn "Reference X1000 V2 absente"
fi

# ----------------------------------------------------------
# 10. CONTROLE FINAL D'INTEGRITE
# ----------------------------------------------------------

section "10. INTEGRITE FINALE"

AFTER_HEAD="$(git rev-parse HEAD)"
AFTER_TREE="$(git rev-parse HEAD^{tree})"

if [[ "$BEFORE_HEAD" == "$AFTER_HEAD" ]]; then
  ok "HEAD Git inchange"
else
  fail "HEAD Git modifie"
fi

if [[ "$BEFORE_TREE" == "$AFTER_TREE" ]]; then
  ok "Arbre du commit Git inchange"
else
  fail "Arbre du commit Git modifie"
fi

if [[ -z "$(git status --porcelain \
  --untracked-files=all)" ]]; then
  ok "Arbre de travail propre"
else
  fail "Modifications detectees apres controle"
fi

# ----------------------------------------------------------
# 11. RAPPORT FINAL
# ----------------------------------------------------------

section "RAPPORT FINAL X1000 V2"

printf 'Controles de fichiers : %s\n' "$CHECKS"
printf 'Erreurs : %s\n' "$ERRORS"
printf 'Avertissements : %s\n' "$WARNINGS"

echo "Mode : diagnostic en lecture seule"
echo "Aucun commit demande"
echo "Aucun push demande"
echo "Aucun deploiement demande"
echo "Aucune publication demandee"
echo "Aucune modification volontaire des FIGES"
echo "Aucune modification volontaire des archives"
echo "Aucune modification volontaire des pronostics"

if (( ERRORS > 0 )); then
  echo "RESULTAT : ECHEC DU CONTROLE"
  exit 1
fi

if (( WARNINGS > 0 )); then
  echo "RESULTAT : CONTROLE AVEC AVERTISSEMENTS"
  exit 0
fi

echo "RESULTAT : CONTROLES STATIQUES REUSSIS"
exit 0
