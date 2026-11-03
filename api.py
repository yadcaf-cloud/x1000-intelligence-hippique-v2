#!/usr/bin/env python3
"""X1000 V2 - API de consultation en lecture seule.

Aucune modification des FIGES, audits ou archives.
Aucune publication automatique.
"""
import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(
    os.environ.get("X1000_DATA_DIR", str(ROOT / "data"))
).resolve()
ORIGIN = os.environ.get("X1000_ALLOWED_ORIGIN", "").rstrip("/")
MAX_FILE = 5_000_000


def load(name):
    path = DATA / name

    if not path.is_file():
        return [], "Fichier absent : " + name

    if path.stat().st_size > MAX_FILE:
        return [], "Fichier trop volumineux : " + name

    try:
        value = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(value, (list, dict)):
            return [], "Format JSON inattendu : " + name

        return value, None

    except (OSError, ValueError) as exc:
        return [], (
            "JSON illisible : " + name
            + " (" + type(exc).__name__ + ")"
        )


def items(value):
    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        if isinstance(value.get("courses"), list):
            return value["courses"]
        return list(value.values())

    return []


def engine(name, course):
    path = ROOT / (name.lower() + ".py")

    if not path.is_file():
        return {
            "moteur": name,
            "statut": "INDISPONIBLE",
            "raison": "Module absent",
            "classement": [],
        }

    try:
        spec = importlib.util.spec_from_file_location(
            "x1000_" + name.lower(), path
        )

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        analyser = getattr(module, "analyser_course", None)

        if not callable(analyser):
            raise ValueError("Fonction analyser_course absente")

        result = analyser(course)

        if not isinstance(result, dict):
            raise ValueError("Resultat invalide")

        return result

    except Exception as exc:
        return {
            "moteur": name,
            "statut": "ERREUR",
            "raison": (
                type(exc).__name__ + ": " + str(exc)[:180]
            ),
            "classement": [],
        }


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
            "application/json; charset=utf-8",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")

        origin = self.headers.get("Origin", "")

        if ORIGIN and origin == ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Vary", "Origin")

        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path

        routes = (
            "/api/status",
            "/api/courses",
            "/api/selections",
            "/api/figes",
            "/api/audits",
            "/api/diagnostic",
        )

        if path not in routes:
            return self.send_json(
                {"erreur": "Route inconnue"}, 404
            )

        courses, err_courses = load("courses.json")
        selections, err_selections = load("selections.json")
        figes, err_figes = load("figes.json")
        audits, err_audits = load("audits.json")

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

        if path == "/api/status":
            return self.send_json({
                "mode": "LECTURE_SEULE_WEB",
                "date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "moteurs": {
                    m: (ROOT / (m.lower() + ".py")).is_file()
                    for m in ("M1", "M2", "M3", "M4", "M5")
                },
                "erreurs": errors,
                "publication": False,
                "figes_automatiques": False,
            })

        if path == "/api/diagnostic":
            return self.send_json({
                "erreurs": errors,
                "data_dir_configure": DATA.is_dir(),
                "origine_autorisee": bool(ORIGIN),
            })

        if path == "/api/courses":
            return self.send_json(courses)

        if path == "/api/figes":
            return self.send_json(figes)

        if path == "/api/audits":
            return self.send_json(audits)

        # Les selections existantes sont prioritaires.
        if items(selections):
            return self.send_json(selections)

        # Analyses temporaires, sans enregistrement.
        output = []

        for course in items(courses)[:100]:
            if not isinstance(course, dict):
                continue

            depart = course.get("depart")

            try:
                date_depart = datetime.fromisoformat(
                    depart.replace("Z", "+00:00")
                )

                if (
                    date_depart.tzinfo is None
                    or date_depart <= datetime.now(timezone.utc)
                ):
                    continue

            except (AttributeError, ValueError):
                continue

            if (
                course.get("localisation_france_verifiee")
                is not True
                or course.get("depart_verifie") is not True
            ):
                continue

            output.append({
                "course_id": course.get("id"),
                "moteurs": {
                    m: engine(m, course)
                    for m in ("M1", "M2", "M3", "M4", "M5")
                },
                "temporaire": True,
                "fige": False,
            })

        return self.send_json(output)

    def do_POST(self):
        self.send_json({"erreur": "Lecture seule"}, 405)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
    )
    args = parser.parse_args()

    ThreadingHTTPServer(
        (args.host, args.port), Handler
    ).serve_forever()
