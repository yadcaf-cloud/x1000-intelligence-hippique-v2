#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX V2.4 — API DE CONSULTATION SECURISEE

- Chargement indépendant des moteurs M1 à M5.
- Utilisation exclusive du paquet moteurs/.
- Validation des courses par le noyau commun.
- Vérification des sorties par chaque moteur.
- Consultation des courses, sélections, FIGÉS et audits.
- Analyses temporaires en mémoire uniquement.
- Diagnostic technique en lecture seule.

INTERDICTIONS :
- Aucune collecte PMU automatique.
- Aucune donnée sportive inventée.
- Aucun FIGÉ automatique ou rétroactif.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucune écriture dans les fichiers de données.

DEMARRAGE :
    python -B api.py --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import sys

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


# ============================================================
# 1. CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA = Path(
    os.environ.get("X1000_DATA_DIR", str(ROOT / "data"))
).resolve()

ORIGIN = os.environ.get(
    "X1000_ALLOWED_ORIGIN", ""
).rstrip("/")

MAX_FILE = 5_000_000
MAX_COURSES_ANALYSEES = 100

MOTEURS = ("M1", "M2", "M3", "M4", "M5")

ROUTES = frozenset({
    "/api/status",
    "/api/courses",
    "/api/selections",
    "/api/figes",
    "/api/audits",
    "/api/diagnostic",
})

FICHIERS = frozenset({
    "courses.json",
    "selections.json",
    "figes.json",
    "audits.json",
})

STATUTS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. CHARGEMENT DU NOYAU ET DES MOTEURS
# ============================================================

def charger_noyau():
    return importlib.import_module(
        "moteurs.noyau_commun"
    )


def engine_path(name):
    if name not in MOTEURS:
        return None

    return ROOT / "moteurs" / f"{name.lower()}.py"


def engine_available(name):
    path = engine_path(name)
    return path is not None and path.is_file()


def charger_moteur(name):
    if name not in MOTEURS:
        raise ValueError("Moteur inconnu")

    if not engine_available(name):
        raise FileNotFoundError(
            f"Fichier du moteur {name} absent"
        )

    module = importlib.import_module(
        f"moteurs.{name.lower()}"
    )

    if getattr(module, "MOTEUR", None) != name:
        raise RuntimeError(
            "Identité du moteur incohérente"
        )

    if str(getattr(module, "VERSION", "")) != "2.4":
        raise RuntimeError(
            "Version du moteur incompatible"
        )

    if not callable(
        getattr(module, "analyser_course", None)
    ):
        raise RuntimeError(
            "Fonction analyser_course absente"
        )

    if not callable(
        getattr(module, "verifier_resultat", None)
    ):
        raise RuntimeError(
            "Fonction verifier_resultat absente"
        )

    return module


# ============================================================
# 3. LECTURE JSON SECURISEE
# ============================================================

def refuser_doublons(paires):
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(
                f"Clé JSON dupliquée : {cle}"
            )
        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur):
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def load(name):
    """
    Retourne (données, erreur).
    Aucune écriture.
    """

    if name not in FICHIERS:
        return [], "Fichier non autorisé"

    path = DATA / name

    try:
        # Refuser les liens symboliques pour éviter
        # une lecture hors du répertoire prévu.
        if path.is_symlink():
            return [], "Lien symbolique interdit"

        if not path.is_file():
            return [], f"Fichier absent : {name}"

        if path.stat().st_size > MAX_FILE:
            return [], f"Fichier trop volumineux : {name}"

        with path.open("rb") as fichier:
            contenu = fichier.read(MAX_FILE + 1)

        if len(contenu) > MAX_FILE:
            return [], f"Fichier trop volumineux : {name}"

        value = json.loads(
            contenu.decode("utf-8"),
            object_pairs_hook=refuser_doublons,
            parse_constant=refuser_constante,
        )

        if not isinstance(value, (list, dict)):
            return [], f"Format JSON invalide : {name}"

        return value, None

    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        OverflowError,
    ) as exc:
        return [], (
            f"Lecture impossible : {name} "
            f"({type(exc).__name__})"
        )


# ============================================================
# 4. EXTRACTION DES COLLECTIONS
# ============================================================

def items(value, collection=None):
    if isinstance(value, list):
        return value

    if not isinstance(value, dict):
        return []

    if collection is not None:
        contenu = value.get(collection)
        return contenu if isinstance(contenu, list) else []

    for cle in ("courses", "selections", "items"):
        contenu = value.get(cle)
        if isinstance(contenu, list):
            return contenu

    return []


# ============================================================
# 5. VALIDATION DES COURSES
# ============================================================

def verifier_course(course):
    try:
        noyau = charger_noyau()

        valide, raison = noyau.verifier_course(
            course
        )

        if type(valide) is not bool:
            return False, "Validation non booléenne"

        return valide, str(raison)

    except Exception as exc:
        return False, (
            "Validation indisponible : "
            + type(exc).__name__
        )


def course_analysable(course):
    valide, _ = verifier_course(course)
    return valide


# ============================================================
# 6. VERIFICATION DES SORTIES M1 A M5
# ============================================================

def verifier_resultat_moteur(
    name,
    course,
    resultat,
    module=None,
):
    if not isinstance(resultat, dict):
        raise ValueError("Résultat moteur invalide")

    if resultat.get("moteur") != name:
        raise ValueError("Identité moteur incohérente")

    if str(resultat.get("version")) != "2.4":
        raise ValueError("Version résultat incorrecte")

    statut = resultat.get("statut")

    if statut not in STATUTS:
        raise ValueError("Statut moteur non autorisé")

    if resultat.get("fige") is not False:
        raise ValueError("FIGÉ interdit")

    if resultat.get("publication") is not False:
        raise ValueError("Publication interdite")

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(classement, list):
        raise ValueError("Classement invalide")

    if not isinstance(partiel, list):
        raise ValueError("Classement partiel invalide")

    if statut == "ANALYSE_DISPONIBLE":
        if len(classement) != 5 or partiel:
            raise ValueError(
                "Cinq positions obligatoires"
            )
    else:
        if classement:
            raise ValueError(
                "Classement complet interdit"
            )

    if len(partiel) > 4:
        raise ValueError(
            "Classement partiel trop long"
        )

    if not isinstance(course, dict):
        raise ValueError("Course invalide")

    partants = course.get("partants", [])

    if not isinstance(partants, list):
        raise ValueError("Partants invalides")

    actifs = {
        cheval["numero"]
        for cheval in partants
        if isinstance(cheval, dict)
        and type(cheval.get("numero")) is int
        and cheval.get("non_partant") is False
    }

    for liste in (classement, partiel):
        numeros = []

        for position, cheval in enumerate(
            liste, start=1
        ):
            if not isinstance(cheval, dict):
                raise ValueError(
                    "Position sportive invalide"
                )

            numero = cheval.get("numero")

            if type(numero) is not int:
                raise ValueError(
                    "Numéro de cheval invalide"
                )

            if numero not in actifs:
                raise ValueError(
                    "Cheval absent ou non-partant"
                )

            if (
                type(cheval.get("position_predite"))
                is not int
                or cheval["position_predite"] != position
            ):
                raise ValueError(
                    "Position prédite incohérente"
                )

            numeros.append(numero)

        if len(numeros) != len(set(numeros)):
            raise ValueError(
                "Cheval présent plusieurs fois"
            )

    # Chaque moteur vérifie ses propres critères,
    # pondérations, scores et classements.
    if module is None:
        module = charger_moteur(name)

    verificateur = getattr(
        module, "verifier_resultat", None
    )

    if not callable(verificateur):
        raise RuntimeError(
            "Vérificateur moteur indisponible"
        )

    verificateur(resultat)

    # Vérifier que la réponse est JSON standard.
    json.dumps(
        resultat,
        ensure_ascii=False,
        allow_nan=False,
    )

    return resultat


# ============================================================
# 7. EXECUTION INDEPENDANTE DES MOTEURS
# ============================================================

def resultat_erreur(name, statut, raison):
    return {
        "moteur": name,
        "statut": statut,
        "raison": raison,
        "classement": [],
        "classement_partiel": [],
        "fige": False,
        "publication": False,
    }


def engine(name, course):
    if name not in MOTEURS:
        return resultat_erreur(
            name, "INDISPONIBLE", "Moteur inconnu"
        )

    if not engine_available(name):
        return resultat_erreur(
            name, "INDISPONIBLE", "Fichier absent"
        )

    valide, raison = verifier_course(course)

    if not valide:
        return resultat_erreur(
            name, "NON_ANALYSABLE", raison
        )

    try:
        module = charger_moteur(name)

        # Isolation de l'entrée de chaque moteur.
        entree = copy.deepcopy(course)
        reference = copy.deepcopy(entree)

        resultat = module.analyser_course(entree)

        if entree != reference:
            raise RuntimeError(
                "Le moteur a modifié son entrée"
            )

        return verifier_resultat_moteur(
            name,
            course,
            resultat,
            module,
        )

    except Exception as exc:
        return resultat_erreur(
            name,
            "ERREUR",
            (
                type(exc).__name__
                + ": "
                + str(exc)[:160]
            ),
        )


# ============================================================
# 8. ANALYSES TEMPORAIRES
# ============================================================

def analyser_courses(courses):
    output = []

    for course in items(courses, "courses"):
        if len(output) >= MAX_COURSES_ANALYSEES:
            break

        valide, raison = verifier_course(course)

        if not valide:
            continue

        resultats = {
            name: engine(name, course)
            for name in MOTEURS
        }

        output.append({
            "course_id": course.get("id"),
            "moteurs": resultats,
            "temporaire": True,
            "fige": False,
            "publication": False,
            "raison_validation": raison,
        })

    return output


# ============================================================
# 9. DIAGNOSTIC TECHNIQUE
# ============================================================

def diagnostic():
    try:
        noyau = charger_noyau()

        noyau_info = {
            "disponible": True,
            "version": getattr(
                noyau, "VERSION", None
            ),
            "validation_disponible": callable(
                getattr(noyau, "verifier_course", None)
            ),
        }

    except Exception as exc:
        noyau_info = {
            "disponible": False,
            "erreur": type(exc).__name__,
        }

    moteurs = {}

    for name in MOTEURS:
        present = engine_available(name)

        info = {
            "present": present,
            "charge": False,
            "version": None,
            "erreur": None,
        }

        if present:
            try:
                module = charger_moteur(name)

                info["charge"] = True
                info["version"] = module.VERSION

            except Exception as exc:
                info["erreur"] = (
                    type(exc).__name__
                    + ": "
                    + str(exc)[:120]
                )

        moteurs[name] = info

    return {
        "mode": "LECTURE_SEULE_WEB",
        "version_api": "2.4",
        "noyau": noyau_info,
        "moteurs": moteurs,
        "data_dir_configure": DATA.is_dir(),
        "origine_autorisee": bool(ORIGIN),
        "collecte_automatique": False,
        "publication": False,
        "figes_automatiques": False,
    }


# ============================================================
# 10. SERVEUR HTTP
# ============================================================

class Handler(BaseHTTPRequestHandler):

    server_version = "X1000-API/2.4"

    def send_json(self, value, status=200):
        try:
            body = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            status = 500
            body = b'{"erreur":"Serialization JSON impossible"}'

        self.send_response(status)

        headers = {
            "Content-Type":
                "application/json; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy":
                "default-src 'none'",
            "Content-Length": str(len(body)),
        }

        for cle, valeur in headers.items():
            self.send_header(cle, valeur)

        origin = self.headers.get("Origin", "")

        if ORIGIN and origin == ORIGIN:
            self.send_header(
                "Access-Control-Allow-Origin",
                ORIGIN,
            )
            self.send_header("Vary", "Origin")

        self.end_headers()

        try:
            self.wfile.write(body)
        except (
            BrokenPipeError,
            ConnectionResetError,
        ):
            pass

    def do_GET(self):
        path = urlsplit(self.path).path

        if path not in ROUTES:
            return self.send_json(
                {"erreur": "Route inconnue"}, 404
            )

        if path == "/api/diagnostic":
            return self.send_json(diagnostic())

        if path == "/api/status":
            return self.send_json({
                "mode": "LECTURE_SEULE_WEB",
                "version": "2.4",
                "date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "moteurs": {
                    name: engine_available(name)
                    for name in MOTEURS
                },
                "collecte_automatique": False,
                "publication": False,
                "figes_automatiques": False,
            })

        correspondance = {
            "/api/courses": "courses.json",
            "/api/selections": "selections.json",
            "/api/figes": "figes.json",
            "/api/audits": "audits.json",
        }

        fichier = correspondance[path]
        donnees, erreur = load(fichier)

        if erreur:
            # Un fichier absent ou illisible ne doit
            # jamais être confondu avec une liste vide.
            return self.send_json(
                {"erreur": erreur},
                503,
            )

        return self.send_json(donnees)

    def do_POST(self):
        return self.methode_interdite()

    def do_PUT(self):
        return self.methode_interdite()

    def do_PATCH(self):
        return self.methode_interdite()

    def do_DELETE(self):
        return self.methode_interdite()

    def do_OPTIONS(self):
        return self.methode_interdite()

    def methode_interdite(self):
        return self.send_json(
            {"erreur": "API en lecture seule"},
            405,
        )


# ============================================================
# 11. DEMARRAGE
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="X1000 V2.4 - API lecture seule"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("Port invalide")

    try:
        serveur = ThreadingHTTPServer(
            (args.host, args.port),
            Handler,
        )

    except OSError as exc:
        print(
            f"Erreur de démarrage : {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        "X1000 PHOENIX V2.4 — API LECTURE SEULE",
        flush=True,
    )

    print(
        f"Adresse : http://{args.host}:{args.port}",
        flush=True,
    )

    try:
        serveur.serve_forever()

    except KeyboardInterrupt:
        pass

    finally:
        serveur.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
