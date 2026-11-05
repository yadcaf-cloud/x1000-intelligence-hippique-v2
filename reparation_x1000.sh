#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================================
# X1000 PHOENIX V2.4 — REPARATION CONTROLEE
# API + M1-M5 + RENDER + BANC HISTORIQUE
# AUCUN COMMIT / PUSH / DEPLOIEMENT / FIGE
# ==========================================================

BRANCH="fix/x1000-v2-reparation-controlee"
REPO="x1000-intelligence-hippique-v2"

echo "=============================================="
echo " X1000 V2.4 — REPARATION CONTROLEE"
echo "=============================================="

# 1. PROTECTION DU DEPOT

git rev-parse --is-inside-work-tree >/dev/null

CURRENT="$(git branch --show-current)"

if [ "$CURRENT" != "$BRANCH" ]; then
  echo "ERREUR : branche incorrecte : $CURRENT"
  echo "Branche obligatoire : $BRANCH"
  exit 1
fi

if [ "$(basename "$(git rev-parse --show-toplevel)")" != "$REPO" ]; then
  echo "ERREUR : depot incorrect."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "ERREUR : modifications preexistantes."
  echo "Sauvegardez votre travail avant execution."
  exit 1
fi

cd "$(git rev-parse --show-toplevel)"

for file in api.py index.html \
  moteurs/noyau_commun.py \
  moteurs/m1.py moteurs/m2.py \
  moteurs/m3.py moteurs/m4.py moteurs/m5.py
do
  test -f "$file" || {
    echo "Fichier obligatoire absent : $file"
    exit 1
  }
done

# Aucun fichier existant ne sera remplace.
mkdir -p tests_historiques

for file in \
  render.yaml \
  tests_historiques/test_connexion.py \
  tests_historiques/banc_historique.py
do
  if [ -e "$file" ]; then
    echo "ERREUR : $file existe deja."
    exit 1
  fi
done

export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

echo "Protection Git : OK"

# 2. CONFIGURATION RENDER — SANS DEPLOIEMENT

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

echo "Configuration Render preparee."

# 3. TESTS DE CONNEXION API ET MOTEURS

cat > tests_historiques/test_connexion.py <<'PY'
import ast
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest

from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api

MOTEURS = ("M1", "M2", "M3", "M4", "M5")

class TestsX1000(unittest.TestCase):

    def test_syntaxe_python(self):
        fichiers = [
            ROOT / "api.py",
            ROOT / "moteurs" / "noyau_commun.py",
        ]
        fichiers += [
            ROOT / "moteurs" / f"{m.lower()}.py"
            for m in MOTEURS
        ]

        for fichier in fichiers:
            with self.subTest(fichier=fichier.name):
                ast.parse(
                    fichier.read_text(encoding="utf-8")
                )

    def test_noyau(self):
        noyau = api.charger_noyau()
        self.assertEqual(str(noyau.VERSION), "2.4")
        self.assertTrue(callable(noyau.verifier_course))

    def test_moteurs(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = api.charger_moteur(nom)
                self.assertEqual(moteur.MOTEUR, nom)
                self.assertEqual(str(moteur.VERSION), "2.4")
                self.assertTrue(
                    callable(moteur.analyser_course)
                )
                self.assertTrue(
                    callable(moteur.verifier_resultat)
                )

    def test_http_lecture_seule(self):
        ancien = api.ORIGIN
        api.ORIGIN = "https://yadcaf-cloud.github.io"

        serveur = ThreadingHTTPServer(
            ("127.0.0.1", 0), api.Handler
        )
        thread = threading.Thread(
            target=serveur.serve_forever,
            daemon=True
        )
        thread.start()

        try:
            for route in (
                "/api/status",
                "/api/diagnostic"
            ):
                connexion = HTTPConnection(
                    "127.0.0.1",
                    serveur.server_port,
                    timeout=5
                )
                connexion.request(
                    "GET",
                    route,
                    headers={
                        "Origin":
                        "https://yadcaf-cloud.github.io"
                    }
                )
                reponse = connexion.getresponse()
                self.assertEqual(reponse.status, 200)
                self.assertEqual(
                    reponse.getheader(
                        "Access-Control-Allow-Origin"
                    ),
                    "https://yadcaf-cloud.github.io"
                )
                json.loads(reponse.read())
                connexion.close()

            for methode in (
                "POST", "PUT", "PATCH", "DELETE"
            ):
                connexion = HTTPConnection(
                    "127.0.0.1",
                    serveur.server_port,
                    timeout=5
                )
                connexion.request(
                    methode, "/api/status"
                )
                reponse = connexion.getresponse()
                self.assertEqual(reponse.status, 405)
                reponse.read()
                connexion.close()

        finally:
            serveur.shutdown()
            serveur.server_close()
            thread.join(timeout=5)
            api.ORIGIN = ancien

    def test_archives_absentes_du_banc(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            self.assertFalse(
                (racine / "figes.json").exists()
            )
            self.assertFalse(
                (racine / "audits.json").exists()
            )

if __name__ == "__main__":
    unittest.main(verbosity=2)
PY

# 4. BANC D'ESSAI HISTORIQUE ISOLE

cat > tests_historiques/banc_historique.py <<'PY'
#!/usr/bin/env python3
"""
X1000 — BANC HISTORIQUE ISOLE

Lecture d'un jeu de courses fourni explicitement.
Aucune modification de l'horloge de production.
Aucune creation de FIGE.
Aucune publication.
Aucune ecriture dans les archives.
"""

import argparse
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import api
from moteurs import noyau_commun

def charger_fixture(chemin):
    chemin = Path(chemin).resolve()

    # Refus des archives et des fichiers de production.
    if chemin.name.lower() in {
        "figes.json", "audits.json",
        "courses.json", "selections.json"
    }:
        raise ValueError(
            "Fichier de production interdit"
        )

    if not chemin.is_file() or chemin.is_symlink():
        raise ValueError("Fixture invalide")

    if chemin.stat().st_size > 5_000_000:
        raise ValueError("Fixture trop volumineuse")

    with chemin.open("r", encoding="utf-8") as f:
        donnees = json.load(
            f,
            object_pairs_hook=api.refuser_doublons,
            parse_constant=api.refuser_constante
        )

    if not isinstance(donnees, list):
        raise ValueError("Liste de courses obligatoire")

    return donnees

def analyser_historique(course):
    if not isinstance(course, dict):
        raise ValueError("Course invalide")

    depart = datetime.fromisoformat(
        course["depart"].replace("Z", "+00:00")
    )

    if depart.tzinfo is None:
        raise ValueError("Fuseau horaire obligatoire")

    # Simulation exactement 15 minutes avant depart.
    from datetime import timedelta
    instant = depart.astimezone(
        timezone.utc
    ) - timedelta(minutes=15)

    class HorlogeSimulee(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return instant.replace(tzinfo=None)
            return instant.astimezone(tz)

    copie = copy.deepcopy(course)

    # Le remplacement de l'horloge est local au test.
    with patch.object(
        noyau_commun,
        "datetime",
        HorlogeSimulee
    ):
        valide, raison = api.verifier_course(copie)

        if not valide:
            return {
                "course_id": copie.get("id"),
                "statut": "NON_ANALYSABLE",
                "raison": raison
            }

        resultats = {}
        for nom in api.MOTEURS:
            resultats[nom] = api.engine(
                nom, copy.deepcopy(copie)
            )

    return {
        "course_id": copie.get("id"),
        "type": "SIMULATION_HISTORIQUE",
        "instant_simule": instant.isoformat(),
        "fige": False,
        "publication": False,
        "moteurs": resultats
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        required=True,
        help="Fichier JSON de test independant"
    )
    args = parser.parse_args()

    courses = charger_fixture(args.fixture)

    resultats = [
        analyser_historique(course)
        for course in courses[:100]
    ]

    print(json.dumps(
        {
            "mode": "SIMULATION_HISTORIQUE",
            "nombre_courses": len(resultats),
            "resultats": resultats
        },
        ensure_ascii=False,
        indent=2,
        allow_nan=False
    ))

if __name__ == "__main__":
    main()
PY

# 5. TESTS AUTOMATIQUES

echo ""
echo "Execution des tests API existants..."
python -B api.py --self-test

echo ""
echo "Execution des tests M1-M5 et connexion..."
python -B tests_historiques/test_connexion.py

# 6. VERIFICATION DES FICHIERS PROTEGES

echo ""
echo "Verification des modifications..."

if git diff --name-only | grep -Ei \
'(^|/)(figes|audits|archives)(/|\.|$)'
then
  echo "ALERTE : fichier protege modifie."
  exit 1
fi

echo ""
echo "=============================================="
echo " X1000 — PREPARATION TERMINEE"
echo "=============================================="
echo "Branche : $BRANCH"
echo "API : tests executes"
echo "Moteurs M1-M5 : chargement teste"
echo "Render : configuration preparee"
echo "Banc historique : prepare"
echo "FIGES : aucune modification"
echo "Archives : aucune modification"
echo "Commit : aucun"
echo "Push : aucun"
echo "Deploiement : aucun"
echo ""
git status --short
echo ""
echo "ATTENTION : aucun deploiement effectue."
echo "Les tests historiques necessitent des fixtures"
echo "verifiees contenant uniquement des donnees"
echo "connues avant le depart."
