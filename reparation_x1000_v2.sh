#!/usr/bin/env bash
set -Eeuo pipefail

# X1000 — Intelligence Hippique Humaine V2
# Réparation contrôlée : interface, API, moteurs, tests et Render.
# Aucun commit, push, déploiement, FIGÉ ou changement d'archives.

BRANCH='fix/x1000-v2-reparation-controlee'
REPO='x1000-intelligence-hippique-v2'
NAME='X1000 — Intelligence Hippique Humaine V2'

fail() { printf 'ERREUR : %s\n' "$*" >&2; exit 1; }
info() { printf '\n=== %s ===\n' "$*"; }
command -v git >/dev/null || fail 'Git absent'
command -v python3 >/dev/null || fail 'Python 3 absent'
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail 'Exécuter dans un dépôt Git'
cd "$(git rev-parse --show-toplevel)"
[[ "$(basename "$PWD")" == "$REPO" ]] || fail "Dépôt incorrect : $PWD"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Branche obligatoire : $BRANCH"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail 'Dépôt non propre : sauvegardez vos changements avant de continuer'
for f in index.html moteurs/noyau_commun.py moteurs/m1.py moteurs/m2.py moteurs/m3.py moteurs/m4.py moteurs/m5.py; do
  [[ -f "$f" && ! -L "$f" ]] || fail "Fichier obligatoire absent ou lien symbolique : $f"
done
for f in api.py render.yaml tests_historiques/test_connexion.py tests_historiques/banc_historique.py; do
  [[ ! -e "$f" && ! -L "$f" ]] || fail "Fichier déjà présent : $f (aucun remplacement automatique)"
done
[[ ! -L tests_historiques ]] || fail 'tests_historiques est un lien symbolique'
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
info "Préparation : $NAME"

# Sauvegarde de l'interface pour restauration en cas d'échec.
BACKUP="$(mktemp)"
cp index.html "$BACKUP"
CREATED=()
SUCCESS=0
cleanup() {
  if [[ "$SUCCESS" != 1 ]]; then
    cp "$BACKUP" index.html
    for f in "${CREATED[@]}"; do rm -f -- "$f"; done
    echo 'Échec : interface restaurée et nouveaux fichiers supprimés.' >&2
  fi
  rm -f "$BACKUP"
}
trap cleanup EXIT

python3 - <<'PY'
from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('🇸🇳🧠🔥 X1000 V2 — Intelligence Hippique','🇸🇳🧠🔥 X1000 — Intelligence Hippique Humaine V2')
s=s.replace('X1000 PHOENIX V2.4','X1000 — Intelligence Hippique Humaine V2')
s=s.replace('X1000 PHOENIX','X1000 — Intelligence Hippique Humaine V2')
p.write_text(s,encoding='utf-8')
print('Identité du tableau de bord harmonisée.')
PY

cat > api.py <<'PY'
#!/usr/bin/env python3
"""API de consultation X1000 V2 : aucune écriture, collecte ou FIGÉ."""
from __future__ import annotations
import argparse
import importlib
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = '2.4'
MOTEURS = ('M1', 'M2', 'M3', 'M4', 'M5')
ORIGIN = os.environ.get('X1000_ALLOWED_ORIGIN', 'https://yadcaf-cloud.github.io')
MAX_BYTES = 5 * 1024 * 1024


def refuser_doublons(paires):
    objet = {}
    for cle, valeur in paires:
        if cle in objet:
            raise ValueError('Clé JSON dupliquée : ' + cle)
        objet[cle] = valeur
    return objet


def refuser_constante(valeur):
    raise ValueError('Constante JSON interdite : ' + valeur)


def charger_noyau():
    return importlib.import_module('moteurs.noyau_commun')


def charger_moteur(nom):
    if nom not in MOTEURS:
        raise ValueError('Moteur inconnu')
    return importlib.import_module('moteurs.' + nom.lower())


def verifier_course(course):
    return charger_noyau().verifier_course(course)


def engine(nom, course):
    return charger_moteur(nom).analyser_course(course)


def lire_collection(nom):
    # Pas de parcours arbitraire : noms fixes et répertoire racine seulement.
    if nom not in ('courses', 'selections', 'figes', 'audits'):
        raise ValueError('Collection inconnue')
    chemin = ROOT / (nom + '.json')
    if not chemin.exists():
        return []
    if chemin.is_symlink() or not chemin.is_file():
        raise ValueError('Fichier de données non régulier')
    if chemin.stat().st_size > MAX_BYTES:
        raise ValueError('Fichier de données trop volumineux')
    with chemin.open(encoding='utf-8') as entree:
        valeur = json.load(entree, object_pairs_hook=refuser_doublons,
                           parse_constant=refuser_constante)
    if not isinstance(valeur, list):
        raise ValueError('Collection JSON non conforme : liste attendue')
    return valeur


def diagnostic():
    moteurs = []
    for nom in MOTEURS:
        try:
            module = charger_moteur(nom)
            valide = (getattr(module, 'MOTEUR', None) == nom and
                      str(getattr(module, 'VERSION', '')) == VERSION and
                      callable(getattr(module, 'analyser_course', None)) and
                      callable(getattr(module, 'verifier_resultat', None)))
            moteurs.append({'moteur': nom, 'etat': 'PRÉSENT' if valide else 'INCOMPATIBLE'})
        except Exception:
            moteurs.append({'moteur': nom, 'etat': 'ERREUR'})
    return {'nom': 'X1000 — Intelligence Hippique Humaine V2',
            'version_technique': VERSION, 'mode': 'LECTURE_SEULE', 'moteurs': moteurs}


class Handler(BaseHTTPRequestHandler):
    def _repondre(self, statut, corps):
        contenu = json.dumps(corps, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(statut)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(contenu)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if self.headers.get('Origin') == ORIGIN:
            self.send_header('Access-Control-Allow-Origin', ORIGIN)
            self.send_header('Vary', 'Origin')
        self.end_headers()
        self.wfile.write(contenu)

    def do_GET(self):
        route = self.path.split('?', 1)[0]
        try:
            if route == '/api/status':
                self._repondre(200, {'status': 'ok', 'mode': 'LECTURE_SEULE',
                                    'version': VERSION, 'moteurs': diagnostic()['moteurs']})
            elif route == '/api/diagnostic':
                self._repondre(200, diagnostic())
            elif route in ('/api/courses', '/api/selections', '/api/figes', '/api/audits'):
                nom = route.removeprefix('/api/')
                self._repondre(200, {nom: lire_collection(nom)})
            else:
                self._repondre(404, {'erreur': 'Route inconnue'})
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
            self._repondre(503, {'erreur': 'Données indisponibles ou invalides'})

    def _interdit(self):
        self._repondre(405, {'erreur': 'Méthode interdite : lecture seule'})
    do_POST = do_PUT = do_PATCH = do_DELETE = _interdit


def self_test():
    noyau = charger_noyau()
    assert str(noyau.VERSION) == VERSION
    assert callable(noyau.verifier_course)
    for nom in MOTEURS:
        module = charger_moteur(nom)
        assert module.MOTEUR == nom
        assert str(module.VERSION) == VERSION
        assert callable(module.analyser_course)
        assert callable(module.verifier_resultat)
    print('API : contrôles des interfaces M1–M5 OK')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
PY
CREATED+=(api.py)

cat > render.yaml <<'YAML'
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
CREATED+=(render.yaml)

mkdir -p tests_historiques
cat > tests_historiques/test_connexion.py <<'PY'
#!/usr/bin/env python3
"""Tests locaux sans écriture dans les données ni archives."""
import ast
import json
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import api


class TestsX1000(unittest.TestCase):
    def test_syntaxe(self):
        for chemin in [ROOT / 'api.py', ROOT / 'moteurs/noyau_commun.py'] + [
            ROOT / 'moteurs' / f'm{i}.py' for i in range(1, 6)
        ]:
            with self.subTest(fichier=chemin.name):
                ast.parse(chemin.read_text(encoding='utf-8'))

    def test_interfaces(self):
        api.self_test()

    def test_http(self):
        serveur = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        thread = threading.Thread(target=serveur.serve_forever, daemon=True)
        thread.start()
        try:
            for route in ('/api/status', '/api/diagnostic', '/api/courses',
                          '/api/selections', '/api/figes', '/api/audits'):
                with self.subTest(route=route):
                    connexion = HTTPConnection('127.0.0.1', serveur.server_port, timeout=5)
                    connexion.request('GET', route, headers={'Origin': api.ORIGIN})
                    reponse = connexion.getresponse()
                    self.assertEqual(reponse.status, 200)
                    self.assertEqual(reponse.getheader('Access-Control-Allow-Origin'), api.ORIGIN)
                    json.loads(reponse.read())
                    connexion.close()
            for methode in ('POST', 'PUT', 'PATCH', 'DELETE'):
                connexion = HTTPConnection('127.0.0.1', serveur.server_port, timeout=5)
                connexion.request(methode, '/api/status')
                reponse = connexion.getresponse()
                self.assertEqual(reponse.status, 405)
                reponse.read()
                connexion.close()
        finally:
            serveur.shutdown()
            serveur.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
PY
CREATED+=(tests_historiques/test_connexion.py)

cat > tests_historiques/banc_historique.py <<'PY'
#!/usr/bin/env python3
"""Simulation historique isolée, sans FIGÉ ni modification d'archives."""
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


def charger_fixture(nom):
    chemin = Path(nom)
    if chemin.name.lower() in INTERDITS or chemin.is_symlink():
        raise ValueError('Fichier de production interdit')
    chemin = chemin.resolve(strict=True)
    if chemin.name.lower() in INTERDITS or not chemin.is_file():
        raise ValueError('Fixture invalide')
    if chemin.stat().st_size > 5_000_000:
        raise ValueError('Fixture trop volumineuse')
    with chemin.open(encoding='utf-8') as f:
        courses = json.load(f, object_pairs_hook=api.refuser_doublons,
                            parse_constant=api.refuser_constante)
    if not isinstance(courses, list):
        raise ValueError('Liste de courses obligatoire')
    return courses


def analyser_historique(course):
    if not isinstance(course, dict):
        raise ValueError('Course invalide')
    depart = datetime.fromisoformat(course['depart'].replace('Z', '+00:00'))
    if depart.tzinfo is None or depart.utcoffset() is None:
        raise ValueError('Fuseau horaire obligatoire')
    instant = depart.astimezone(timezone.utc) - timedelta(minutes=15)

    class HorlogeSimulee(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant.replace(tzinfo=None)
            return instant.astimezone(tz)

    copie = copy.deepcopy(course)
    with patch.object(noyau_commun, 'datetime', HorlogeSimulee):
        valide, raison = api.verifier_course(copie)
        if not valide:
            return {'course_id': copie.get('id'), 'statut': 'NON_ANALYSABLE',
                    'raison': raison}
        resultats = {nom: api.engine(nom, copy.deepcopy(copie)) for nom in api.MOTEURS}
    return {'course_id': copie.get('id'), 'type': 'SIMULATION_HISTORIQUE',
            'instant_simule': instant.isoformat(), 'fige': False,
            'publication': False, 'moteurs': resultats}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    args = parser.parse_args()
    courses = charger_fixture(args.fixture)
    resultats = [analyser_historique(c) for c in courses[:100]]
    print(json.dumps({'mode': 'SIMULATION_HISTORIQUE',
                      'nombre_courses': len(resultats), 'resultats': resultats},
                     ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
PY
CREATED+=(tests_historiques/banc_historique.py)

info 'Contrôles statiques et tests locaux'
python3 -B api.py --self-test
python3 -B tests_historiques/test_connexion.py
python3 - <<'PY'
from pathlib import Path
import ast
for p in (Path('api.py'), Path('tests_historiques/test_connexion.py'),
          Path('tests_historiques/banc_historique.py')):
    ast.parse(p.read_text(encoding='utf-8'))
print('Syntaxe des nouveaux fichiers : OK')
PY

git diff --check
if git diff --name-only | grep -Eiq '(^|/)(figes|audits|archives)(/|\.|$)'; then
  fail 'Fichier protégé modifié'
fi
if git ls-files --others --exclude-standard | grep -Eiq '(^|/)(figes|audits|archives)(/|\.|$)'; then
  fail 'Nouveau fichier protégé détecté'
fi
SUCCESS=1
info 'Préparation terminée (sans commit, push ni déploiement)'
git status --short
printf '\nPour examiner : git diff -- index.html\n'
printf 'Les tests historiques exigent une fixture indépendante ne contenant que des données connues avant le départ.\n'
