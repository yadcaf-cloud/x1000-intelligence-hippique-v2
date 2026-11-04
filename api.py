#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 — API de consultation sécurisée.

- Chargement des moteurs M1 à M5.
- Correction du chargement de M1.
- Consultation des courses et sélections.
- Consultation des FIGÉS et audits.
- Analyses temporaires avant départ.
- Aucun FIGÉ automatique.
- Aucune modification des archives.
- Aucune publication automatique.
"""

import argparse
import importlib
import importlib.util
import json
import os

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent

DATA = Path(
    os.environ.get(
        "X1000_DATA_DIR",
        str(ROOT / "data")
    )
).resolve()

ORIGIN = os.environ.get(
    "X1000_ALLOWED_ORIGIN", ""
).rstrip("/")

MAX_FILE = 5_000_000

MOTEURS = ("M1", "M2", "M3", "M4", "M5")

ROUTES = (
    "/api/status",
    "/api/courses",
    "/api/selections",
    "/api/figes",
    "/api/audits",
    "/api/diagnostic",
)


# ============================================================
# 1. LECTURE SÉCURISÉE DES DONNÉES
# ============================================================

def load(name):
    path = DATA / name

    try:
        if not path.is_file():
            return [], "Fichier absent : " + name

        if path.stat().st_size > MAX_FILE:
            return [], "Fichier trop volumineux : " + name

        value = json.loads(
            path.read_text(encoding="utf-8")
        )

        if not isinstance(value, (list, dict)):
            return [], "Format JSON inattendu : " + name

        return value, None

    except (OSError, ValueError) as exc:
        return [], (
            "JSON illisible : "
            + name
            + " ("
            + type(exc).__name__
            + ")"
        )


def items(value):
    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        if isinstance(value.get("courses"), list):
            return value["courses"]

        return list(value.values())

    return []


# ============================================================
# 2. LOCALISATION DES MOTEURS
# ============================================================

def engine_path(name):
    if name not in MOTEURS:
        return None

    if name == "M1":
        return ROOT / "moteurs" / "m1.py"

    return ROOT / (name.lower() + ".py")


def engine_available(name):
    path = engine_path(name)

    return bool(
        path is not None and path.is_file()
    )


# ============================================================
# 3. CHARGEMENT ET EXÉCUTION M1 À M5
# ============================================================

def engine(name, course):

    if name not in MOTEURS:
        return {
            "moteur": name,
            "statut": "INDISPONIBLE",
            "raison": "Moteur inconnu",
            "classement": [],
        }

    path = engine_path(name)

    if path is None or not path.is_file():
        return {
            "moteur": name,
            "statut": "INDISPONIBLE",
            "raison": "Module absent",
            "classement": [],
        }

    try:

        # M1 doit être chargé comme module du paquet
        # moteurs afin de résoudre .noyau_commun.

        if name == "M1":
            module = importlib.import_module(
                "moteurs.m1"
            )

        else:
            spec = importlib.util.spec_from_file_location(
                "x1000_" + name.lower(),
                path
            )

            if spec is None or spec.loader is None:
                raise ImportError(
                    "Impossible de charger " + name
                )

            module = importlib.util.module_from_spec(
                spec
            )

            spec.loader.exec_module(module)

        analyser = getattr(
            module,
            "analyser_course",
            None
        )

        if not callable(analyser):
            raise ValueError(
                "Fonction analyser_course absente"
            )

        result = analyser(course)

        if not isinstance(result, dict):
            raise ValueError(
                "Résultat moteur invalide"
            )

        return result

    except Exception as exc:
        return {
            "moteur": name,
            "statut": "ERREUR",
            "raison": (
                type(exc).__name__
                + ": "
                + str(exc)[:180]
            ),
            "classement": [],
        }


# ============================================================
# 4. CONTRÔLE DES COURSES AVANT DÉPART
# ============================================================

def course_analysable(course):

    if not isinstance(course, dict):
        return False

    if (
        course.get("localisation_france_verifiee")
        is not True
    ):
        return False

    if course.get("depart_verifie") is not True:
        return False

    depart = course.get("depart")

    if not isinstance(depart, str):
        return False

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )

        if date_depart.tzinfo is None:
            return False

        if date_depart <= datetime.now(
            timezone.utc
        ):
            return False

    except (ValueError, TypeError, OverflowError):
        return False

    return True


# ============================================================
# 5. ANALYSES TEMPORAIRES
# ============================================================

def analyser_courses(courses):

    output = []

    for course in items(courses)[:100]:

        if not course_analysable(course):
            continue

        resultats = {}

        for moteur in MOTEURS:
            resultats[moteur] = engine(
                moteur,
                course
            )

        output.append({
            "course_id": course.get("id"),
            "moteurs": resultats,
            "temporaire": True,
            "fige": False,
        })

    return output


# ============================================================
# 6. SERVEUR HTTP EN LECTURE SEULE
# ============================================================

class Handler(BaseHTTPRequestHandler):

    def send_json(self, value, status=200):

        body = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff"
        )

        self.send_header(
            "X-Frame-Options",
            "DENY"
        )

        origin = self.headers.get("Origin", "")

        if ORIGIN and origin == ORIGIN:
            self.send_header(
                "Access-Control-Allow-Origin",
                ORIGIN
            )
            self.send_header(
                "Vary",
                "Origin"
            )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):

        path = urlsplit(self.path).path

        if path not in ROUTES:
            return self.send_json(
                {"erreur": "Route inconnue"},
                404
            )

        courses, err_courses = load(
            "courses.json"
        )

        selections, err_selections = load(
            "selections.json"
        )

        figes, err_figes = load(
            "figes.json"
        )

        audits, err_audits = load(
            "audits.json"
        )

        errors = {
            key: value
            for key, value in [
                ("courses", err_courses),
                ("selections", err_selections),
                ("figes", err_figes),
                ("audits", err_audits),
            ]
            if value
        }

        # ----------------------------------------------------
        # STATUT GÉNÉRAL
        # ----------------------------------------------------

        if path == "/api/status":

            return self.send_json({
                "mode": "LECTURE_SEULE_WEB",

                "date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),

                "moteurs": {
                    m: engine_available(m)
                    for m in MOTEURS
                },

                "erreurs": errors,

                "publication": False,

                "figes_automatiques": False,
            })

        # ----------------------------------------------------
        # DIAGNOSTIC
        # ----------------------------------------------------

        if path == "/api/diagnostic":

            return self.send_json({
                "erreurs": errors,

                "data_dir_configure": DATA.is_dir(),

                "origine_autorisee": bool(ORIGIN),

                "moteurs_presents": {
                    m: engine_available(m)
                    for m in MOTEURS
                },

                "mode": "LECTURE_SEULE_WEB",
            })

        # ----------------------------------------------------
        # COURSES
        # ----------------------------------------------------

        if path == "/api/courses":
            return self.send_json(courses)

        # ----------------------------------------------------
        # FIGÉS : CONSULTATION UNIQUEMENT
        # ----------------------------------------------------

        if path == "/api/figes":
            return self.send_json(figes)

        # ----------------------------------------------------
        # AUDITS : CONSULTATION UNIQUEMENT
        # ----------------------------------------------------

        if path == "/api/audits":
            return self.send_json(audits)

        # ----------------------------------------------------
        # SÉLECTIONS
        # ----------------------------------------------------

        if items(selections):
            return self.send_json(selections)

        # Aucune sélection enregistrée :
        # calcul temporaire uniquement.

        output = analyser_courses(courses)

        return self.send_json(output)

    # --------------------------------------------------------
    # INTERDICTION DES MODIFICATIONS HTTP
    # --------------------------------------------------------

    def do_POST(self):
        self.send_json(
            {"erreur": "Lecture seule"},
            405
        )

    def do_PUT(self):
        self.send_json(
            {"erreur": "Lecture seule"},
            405
        )

    def do_PATCH(self):
        self.send_json(
            {"erreur": "Lecture seule"},
            405
        )

    def do_DELETE(self):
        self.send_json(
            {"erreur": "Lecture seule"},
            405
        )


# ============================================================
# 7. DÉMARRAGE DE L'API
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="X1000 V2 - API lecture seule"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(
            os.environ.get("PORT", "8000")
        )
    )

    args = parser.parse_args()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        Handler
    )

    print(
        "X1000 V2 — API lecture seule",
        flush=True
    )

    print(
        "Adresse : http://"
        + args.host
        + ":"
        + str(args.port),
        flush=True
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        pass

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
