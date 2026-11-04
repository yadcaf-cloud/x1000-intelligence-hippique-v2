#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - API DE CONSULTATION SECURISEE

Fonctions :
- Chargement uniforme des moteurs M1 a M5.
- Utilisation exclusive du paquet moteurs/.
- Validation des courses par le noyau commun.
- Consultation des courses et selections.
- Consultation des FIGES et audits.
- Analyses sportives temporaires avant depart.
- Verification des classements des moteurs.
- Diagnostic technique en lecture seule.

Interdictions :
- Aucune collecte PMU automatique.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucune ecriture dans les fichiers de donnees.

Execution :
    python api.py --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


# ============================================================
# 1. CONFIGURATION GENERALE
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA = Path(
    os.environ.get(
        "X1000_DATA_DIR",
        str(ROOT / "data"),
    )
).resolve()

ORIGIN = os.environ.get(
    "X1000_ALLOWED_ORIGIN",
    "",
).rstrip("/")

MAX_FILE = 5_000_000
MAX_COURSES_ANALYSEES = 100

MOTEURS = (
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
)

ROUTES = (
    "/api/status",
    "/api/courses",
    "/api/selections",
    "/api/figes",
    "/api/audits",
    "/api/diagnostic",
)

FICHIERS_AUTORISES = frozenset({
    "courses.json",
    "selections.json",
    "figes.json",
    "audits.json",
})

STATUTS_MOTEURS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. CHARGEMENT DU NOYAU COMMUN
# ============================================================

def charger_noyau():
    """
    Charge le noyau technique commun.

    Aucun repli vers les anciens modules.
    """

    return importlib.import_module(
        "moteurs.noyau_commun"
    )


# ============================================================
# 3. LECTURE JSON SECURISEE
# ============================================================

def refuser_doublons(paires):
    """Refuse les cles JSON dupliquees."""

    resultat = {}

    for cle, valeur in paires:

        if cle in resultat:
            raise ValueError(
                f"Cle JSON dupliquee : {cle}"
            )

        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur):
    """Refuse NaN, Infinity et -Infinity."""

    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def load(name):
    """
    Lit uniquement les fichiers autorises.

    Retourne :
        (donnees, erreur)

    Aucun fichier n'est modifie.
    """

    if name not in FICHIERS_AUTORISES:
        return [], "Nom de fichier non autorise"

    path = DATA / name

    try:

        if not path.is_file():
            return [], (
                "Fichier absent : " + name
            )

        if path.stat().st_size > MAX_FILE:
            return [], (
                "Fichier trop volumineux : " + name
            )

        with path.open("rb") as fichier:
            contenu = fichier.read(
                MAX_FILE + 1
            )

        if len(contenu) > MAX_FILE:
            return [], (
                "Fichier trop volumineux : " + name
            )

        value = json.loads(
            contenu.decode("utf-8"),
            object_pairs_hook=refuser_doublons,
            parse_constant=refuser_constante,
        )

        if not isinstance(
            value,
            (list, dict),
        ):
            return [], (
                "Format JSON inattendu : " + name
            )

        return value, None

    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        OverflowError,
    ) as exc:

        return [], (
            "JSON illisible : "
            + name
            + " ("
            + type(exc).__name__
            + ")"
        )


# ============================================================
# 4. EXTRACTION DES COLLECTIONS
# ============================================================

def items(value):
    """
    Extrait les elements d'une collection.

    Les objets JSON uniques ne sont pas
    interpretes comme des listes de courses.
    """

    if isinstance(value, list):
        return value

    if isinstance(value, dict):

        if isinstance(
            value.get("courses"),
            list,
        ):
            return value["courses"]

        if isinstance(
            value.get("selections"),
            list,
        ):
            return value["selections"]

        if isinstance(
            value.get("items"),
            list,
        ):
            return value["items"]

        if (
            value
            and all(
                isinstance(element, dict)
                for element in value.values()
            )
        ):
            return list(value.values())

    return []


# ============================================================
# 5. LOCALISATION DES MOTEURS
# ============================================================

def engine_path(name):
    """
    Utilise exclusivement les moteurs V2.4.

    M1 : moteurs/m1.py
    M2 : moteurs/m2.py
    M3 : moteurs/m3.py
    M4 : moteurs/m4.py
    M5 : moteurs/m5.py
    """

    if name not in MOTEURS:
        return None

    return (
        ROOT
        / "moteurs"
        / (name.lower() + ".py")
    )


def engine_available(name):
    """Verifie la presence physique du moteur."""

    path = engine_path(name)

    return bool(
        path is not None
        and path.is_file()
    )


# ============================================================
# 6. VALIDATION DES COURSES
# ============================================================

def verifier_course(course):
    """
    Applique la validation du noyau commun.

    Controle notamment :
    - Localisation France verifiee.
    - Depart verifie et futur.
    - Depart dans les 30 prochains jours.
    - Partants et non-partants coherents.
    - Au moins cinq partants actifs.
    """

    try:

        noyau = charger_noyau()

        valide, raison = noyau.verifier_course(
            course
        )

        return bool(valide), str(raison)

    except (
        ImportError,
        AttributeError,
        ValueError,
        TypeError,
        RuntimeError,
        OverflowError,
    ) as exc:

        return False, (
            "Validation indisponible : "
            + type(exc).__name__
        )


def course_analysable(course):
    """Compatibilite avec l'ancienne API."""

    valide, _ = verifier_course(course)

    return valide


# ============================================================
# 7. VERIFICATION DES SORTIES SPORTIVES
# ============================================================

def verifier_resultat_moteur(
    name,
    course,
    resultat,
):
    """
    Controle les sorties M1-M5.

    Aucun resultat incomplet ne devient
    une prediction complete.
    """

    if not isinstance(resultat, dict):
        raise ValueError(
            "Resultat moteur invalide"
        )

    if resultat.get("moteur") != name:
        raise ValueError(
            "Identite du moteur incoherente"
        )

    if (
        resultat.get("statut")
        not in STATUTS_MOTEURS
    ):
        raise ValueError(
            "Statut moteur non autorise"
        )

    if resultat.get("fige") is not False:
        raise ValueError(
            "FIGE interdit"
        )

    if resultat.get("publication") is not False:
        raise ValueError(
            "Publication interdite"
        )

    noyau = charger_noyau()

    noyau.verifier_sortie_analyse(
        course,
        resultat,
    )

    return resultat


# ============================================================
# 8. EXECUTION INDEPENDANTE DES MOTEURS
# ============================================================

def engine(name, course):
    """
    Execute un moteur independant.

    Chaque moteur conserve :
    - Ses criteres sportifs.
    - Ses ponderations.
    - Ses scores.
    - Ses cinq positions predites.
    - Ses risques et alertes.

    Aucune publication ni ecriture.
    """

    if name not in MOTEURS:
        return {
            "moteur": name,
            "statut": "INDISPONIBLE",
            "raison": "Moteur inconnu",
            "classement": [],
            "classement_partiel": [],
            "fige": False,
            "publication": False,
        }

    if not engine_available(name):
        return {
            "moteur": name,
            "statut": "INDISPONIBLE",
            "raison": "Module moteur absent",
            "classement": [],
            "classement_partiel": [],
            "fige": False,
            "publication": False,
        }

    try:

        module = importlib.import_module(
            "moteurs." + name.lower()
        )

        analyser = getattr(
            module,
            "analyser_course",
            None,
        )

        if not callable(analyser):
            raise ValueError(
                "Fonction analyser_course absente"
            )

        resultat = analyser(course)

        return verifier_resultat_moteur(
            name,
            course,
            resultat,
        )

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
            "classement_partiel": [],
            "fige": False,
            "publication": False,
        }


# ============================================================
# 9. ANALYSES TEMPORAIRES
# ============================================================

def analyser_courses(courses):
    """
    Analyse au maximum 100 courses.

    Seules les courses techniquement
    admissibles sont analysees.

    Aucune selection n'est enregistree.
    """

    output = []

    for course in items(courses):

        if len(output) >= MAX_COURSES_ANALYSEES:
            break

        valide, raison = verifier_course(
            course
        )

        if not valide:
            continue

        resultats = {}

        for moteur in MOTEURS:

            resultats[moteur] = engine(
                moteur,
                course,
            )

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
# 10. SERVEUR HTTP EN LECTURE SEULE
# ============================================================

class Handler(BaseHTTPRequestHandler):
    """API HTTP sans methode d'ecriture."""

    server_version = "X1000-API/2.4"

    def send_json(
        self,
        value,
        status=200,
    ):
        """Envoie une reponse JSON securisee."""

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

            body = json.dumps({
                "erreur": (
                    "Erreur de serialisation JSON"
                )
            }).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.send_header(
            "X-Frame-Options",
            "DENY",
        )

        self.send_header(
            "Referrer-Policy",
            "no-referrer",
        )

        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'",
        )

        origin = self.headers.get(
            "Origin",
            "",
        )

        if ORIGIN and origin == ORIGIN:

            self.send_header(
                "Access-Control-Allow-Origin",
                ORIGIN,
            )

            self.send_header(
                "Vary",
                "Origin",
            )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        try:
            self.wfile.write(body)

        except (
            BrokenPipeError,
            ConnectionResetError,
        ):
            pass

    # --------------------------------------------------------
    # CONSULTATION HTTP
    # --------------------------------------------------------

    def do_GET(self):

        path = urlsplit(
            self.path
        ).path

        if path not in ROUTES:

            return self.send_json(
                {"erreur": "Route inconnue"},
                404,
            )

        # ----------------------------------------------------
        # CHARGEMENT DES DONNEES
        # ----------------------------------------------------

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
            for key, value in (
                ("courses", err_courses),
                ("selections", err_selections),
                ("figes", err_figes),
                ("audits", err_audits),
            )
            if value
        }

        # ----------------------------------------------------
        # STATUT GENERAL
        # ----------------------------------------------------

        if path == "/api/status":

            return self.send_json({
                "mode": "LECTURE_SEULE_WEB",

                "version": "2.4",

                "date_utc": datetime.now(
                    timezone.utc
                ).isoformat(),

                "moteurs": {
                    moteur: engine_available(
                        moteur
                    )
                    for moteur in MOTEURS
                },

                "erreurs": errors,

                "collecte_automatique": False,

                "publication": False,

                "figes_automatiques": False,
            })

        # ----------------------------------------------------
        # DIAGNOSTIC TECHNIQUE
        # ----------------------------------------------------

        if path == "/api/diagnostic":

            noyau_disponible = False
            noyau_version = None
            noyau_erreur = None

            try:

                noyau = charger_noyau()

                noyau_disponible = True

                noyau_version = getattr(
                    noyau,
                    "VERSION",
                    None,
                )

            except Exception as exc:

                noyau_erreur = (
                    type(exc).__name__
                )

            return self.send_json({
                "mode": "LECTURE_SEULE_WEB",

                "version_api": "2.4",

                "noyau_disponible": (
                    noyau_disponible
                ),

                "version_noyau": (
                    noyau_version
                ),

                "erreur_noyau": (
                    noyau_erreur
                ),

                "data_dir_configure": (
                    DATA.is_dir()
                ),

                "origine_autorisee": bool(
                    ORIGIN
                ),

                "moteurs_presents": {
                    moteur: engine_available(
                        moteur
                    )
                    for moteur in MOTEURS
                },

                "erreurs": errors,

                "collecte_automatique": False,

                "publication": False,

                "figes_automatiques": False,
            })

        # ----------------------------------------------------
        # COURSES
        # ----------------------------------------------------

        if path == "/api/courses":

            return self.send_json(
                courses
            )

        # ----------------------------------------------------
        # FIGES : CONSULTATION UNIQUEMENT
        # ----------------------------------------------------

        if path == "/api/figes":

            return self.send_json(
                figes
            )

        # ----------------------------------------------------
        # AUDITS : CONSULTATION UNIQUEMENT
        # ----------------------------------------------------

        if path == "/api/audits":

            return self.send_json(
                audits
            )

        # ----------------------------------------------------
        # SELECTIONS
        # ----------------------------------------------------

        if path == "/api/selections":

            if items(selections):

                return self.send_json(
                    selections
                )

            # Aucun enregistrement disponible :
            # calcul temporaire en memoire uniquement.

            output = analyser_courses(
                courses
            )

            return self.send_json(
                output
            )

    # --------------------------------------------------------
    # METHODES HTTP INTERDITES
    # --------------------------------------------------------

    def do_POST(self):

        return self.send_json(
            {"erreur": "Lecture seule"},
            405,
        )

    def do_PUT(self):

        return self.send_json(
            {"erreur": "Lecture seule"},
            405,
        )

    def do_PATCH(self):

        return self.send_json(
            {"erreur": "Lecture seule"},
            405,
        )

    def do_DELETE(self):

        return self.send_json(
            {"erreur": "Lecture seule"},
            405,
        )


# ============================================================
# 11. DEMARRAGE DE L'API
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 - API lecture seule"
        )
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Adresse d'ecoute locale",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(
            os.environ.get(
                "PORT",
                "8000",
            )
        ),
        help="Port HTTP",
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error(
            "Le port doit etre compris "
            "entre 1 et 65535"
        )

    try:

        serveur = ThreadingHTTPServer(
            (
                args.host,
                args.port,
            ),
            Handler,
        )

    except OSError as exc:

        print(
            "Erreur de demarrage API : "
            + str(exc),
            file=sys.stderr,
        )

        return 1

    print(
        "X1000 V2.4 - API lecture seule",
        flush=True,
    )

    print(
        "Adresse : http://"
        + args.host
        + ":"
        + str(args.port),
        flush=True,
    )

    try:

        serveur.serve_forever()

    except KeyboardInterrupt:
        pass

    finally:
        serveur.server_close()

    return 0


# ============================================================
# 12. EXECUTION
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
