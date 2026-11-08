
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# X1000 — INTELLIGENCE HIPPIQUE V2
# PREPARATION CONTROLEE — API, M1-M5, RENDER, TESTS
# AUCUN COMMIT / PUSH / DEPLOIEMENT / FIGE
# ==========================================================

BRANCH="fix/x1000-v2-reparation-controlee"
REPO="x1000-intelligence-hippique-v2"
ROOT="$(git rev-parse --show-toplevel)"

fail() { printf 'ERREUR : %s\n' "$*" >&2; exit 1; }
trap 'printf "ERREUR : interruption a la ligne %s. Verifiez git status --short.\n" "$LINENO" >&2' ERR

[[ "$(git rev-parse --is-inside-work-tree)" == true ]] || fail "Hors depot Git"
[[ "$(basename "$ROOT")" == "$REPO" ]] || fail "Depot incorrect"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Branche obligatoire : $BRANCH"
cd "$ROOT"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "Depot non propre : sauvegardez vos modifications"

for file in api.py index.html moteurs/noyau_commun.py moteurs/m1.py moteurs/m2.py moteurs/m3.py moteurs/m4.py moteurs/m5.py; do
  [[ -f "$file" && ! -L "$file" ]] || fail "Fichier obligatoire absent ou lien symbolique : $file"
done

for file in render.yaml tests_historiques tests_historiques/test_connexion.py tests_historiques/banc_historique.py; do
  [[ ! -e "$file" && ! -L "$file" ]] || fail "Chemin deja existant : $file (aucun remplacement)"
done

export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1

# Tests non destructifs avant toute creation de fichier.
python -B - <<'PY'
import ast
from pathlib import Path
for name in ['api.py', 'moteurs/noyau_commun.py'] + [f'moteurs/m{i}.py' for i in range(1, 6)]:
    ast.parse(Path(name).read_text(encoding='utf-8-sig'), filename=name)
    print('SYNTAXE OK:', name)
PY

echo 'Execution du self-test API existant...'
python -B api.py --self-test

# Generation dans un dossier temporaire avant installation.
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/tests_historiques"

cat > "$TMP/render.yaml" <<'YAML'
services:
  - type: web
    name: x1000-v2-api
    runtime: python
    branch: fix/x1000-v2-reparation-controlee
    autoDeployTrigger: "off"
    buildCommand: "python -B api.py --self-test"
    startCommand: "python -B api.py --host 0.0.0.0 --port $PORT"
    healthCheckPath: /api/status
    envVars:
      - key: PYTHONDONTWRITEBYTECODE
        value: "1"
      - key: PYTHONNOUSERSITE
        value: "1"
      - key: X1000_ALLOWED_ORIGIN
        value: https://yadcaf-cloud.github.io
YAML

cat > "$TMP/tests_historiques/test_connexion.py" <<'PY'
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import api

MOTEURS = ('M1', 'M2', 'M3', 'M4', 'M5')

class TestsX1000(unittest.TestCase):
    def test_syntaxe(self):
        for name in ['api.py', 'moteurs/noyau_commun.py'] + [f'moteurs/m{i}.py' for i in range(1, 6)]:
            with self.subTest(name=name):
                ast.parse((ROOT / name).read_text(encoding='utf-8-sig'))

    def test_noyau(self):
        noyau = api.charger_noyau()
        self.assertTrue(str(noyau.VERSION).strip())
        self.assertTrue(callable(noyau.verifier_course))

    def test_moteurs(self):
        noyau = api.charger_noyau()
        for nom in MOTEURS:
            with self.subTest(nom=nom):
                moteur = api.charger_moteur(nom)
                self.assertEqual(moteur.MOTEUR, nom)
                self.assertEqual(str(moteur.VERSION), str(noyau.VERSION))
                self.assertTrue(callable(moteur.analyser_course))
                self.assertTrue(callable(moteur.verifier_resultat))

if __name__ == '__main__':
    unittest.main(verbosity=2)
PY

cat > "$TMP/tests_historiques/banc_historique.py" <<'PY'
#!/usr/bin/env python3
"""Banc historique X1000 V2 : simulation uniquement, aucune publication."""
import argparse
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import api
from moteurs import noyau_commun

INTERDITS = {'figes.json', 'audits.json', 'courses.json', 'selections.json'}

def charger_fixture(chemin):
    original = Path(chemin)
    if original.is_symlink() or original.name.lower() in INTERDITS:
        raise ValueError('Fichier de production ou lien symbolique interdit')
    chemin = original.resolve(strict=True)
    if chemin.name.lower() in INTERDITS or not chemin.is_file():
        raise ValueError('Fixture invalide')
    if chemin.stat().st_size > 5_000_000:
        raise ValueError('Fixture trop volumineuse')
    with chemin.open(encoding='utf-8') as fichier:
        donnees = json.load(fichier, object_pairs_hook=api.refuser_doublons,
                            parse_constant=api.refuser_constante)
    if not isinstance(donnees, list):
        raise ValueError('Liste de courses obligatoire')
    return donnees

def analyser_historique(course):
    if not isinstance(course, dict):
        raise ValueError('Course invalide')
    depart = datetime.fromisoformat(course['depart'].replace('Z', '+00:00'))
    if depart.tzinfo is None:
        raise ValueError('Fuseau horaire obligatoire')
    instant = depart.astimezone(timezone.utc) - timedelta(minutes=15)

    class HorlogeSimulee(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    copie = copy.deepcopy(course)
    with patch.object(noyau_commun, 'datetime', HorlogeSimulee):
        valide, raison = api.verifier_course(copie)
        if not valide:
            return {'course_id': copie.get('id'), 'statut': 'NON_ANALYSABLE', 'raison': raison}
        resultats = {nom: api.engine(nom, copy.deepcopy(copie)) for nom in api.MOTEURS}
    return {'course_id': copie.get('id'), 'type': 'SIMULATION_HISTORIQUE',
            'instant_simule': instant.isoformat(), 'fige': False,
            'publication': False, 'moteurs': resultats}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    args = parser.parse_args()
    resultats = [analyser_historique(c) for c in charger_fixture(args.fixture)[:100]]
    print(json.dumps({'mode': 'SIMULATION_HISTORIQUE', 'nombre_courses': len(resultats),
                      'resultats': resultats}, ensure_ascii=False, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
PY

python -B - "$TMP" <<'PY'
import ast
import sys
from pathlib import Path
root = Path(sys.argv[1])
for name in ('tests_historiques/test_connexion.py', 'tests_historiques/banc_historique.py'):
    ast.parse((root / name).read_text(encoding='utf-8'), filename=name)
print('Tests generes : syntaxe valide')
PY

# Installer sans ecraser les chemins existants.
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "Depot modifie pendant le controle"
for file in render.yaml tests_historiques; do
  [[ ! -e "$file" && ! -L "$file" ]] || fail "Chemin apparu pendant le controle : $file"
done
mv -n -- "$TMP/render.yaml" render.yaml
mv -n -- "$TMP/tests_historiques" tests_historiques

python -B tests_historiques/test_connexion.py

# Interdire toute modification suivie, y compris les FIGES et archives.
[[ -z "$(git diff --name-only HEAD --)" ]] || fail "Fichier suivi modifie"
[[ -z "$(git diff --cached --name-only --)" ]] || fail "Fichier indexe modifie"

printf '\nX1000 V2 : PREPARATION TERMINEE\n'
printf 'Aucun commit, push, deploiement ou FIGE effectue par ce script.\n'
printf 'Nouveaux fichiers de preparation :\n'
git status --short
printf 'ATTENTION : banc historique non execute (fixture independante requise).\n'
