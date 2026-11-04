#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 PHOENIX V2.4 — API de consultation uniquement.

Aucune collecte, écriture de données, publication ou création de FIGÉ.
Exécution : python -B api.py --host 127.0.0.1 --port 8000
Tests : python -B api.py --self-test
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("X1000_DATA_DIR", str(ROOT / "data"))).resolve()
ORIGIN = os.environ.get("X1000_ALLOWED_ORIGIN", "").rstrip("/")
MAX_FILE = 5_000_000
MAX_COURSES_ANALYSEES = 100
MOTEURS = ("M1", "M2", "M3", "M4", "M5")
ROUTES = frozenset(("/api/status", "/api/courses", "/api/selections", "/api/figes", "/api/audits", "/api/diagnostic"))
FICHIERS = frozenset(("courses.json", "selections.json", "figes.json", "audits.json"))
STATUTS = frozenset(("ANALYSE_DISPONIBLE", "DONNEES_INSUFFISANTES", "NON_ANALYSABLE"))
ROUTE_FILES = {"/api/courses": "courses.json", "/api/selections": "selections.json", "/api/figes": "figes.json", "/api/audits": "audits.json"}


def charger_noyau():
    module = importlib.import_module("moteurs.noyau_commun")
    if str(getattr(module, "VERSION", "")) != "2.4":
        raise RuntimeError("Version du noyau incompatible")
    if not callable(getattr(module, "verifier_course", None)):
        raise RuntimeError("Validation du noyau absente")
    return module


def engine_path(name):
    return ROOT / "moteurs" / (name.lower() + ".py") if name in MOTEURS else None


def engine_available(name):
    path = engine_path(name)
    return path is not None and path.is_file() and not path.is_symlink()


def charger_moteur(name):
    if name not in MOTEURS:
        raise ValueError("Moteur inconnu")
    if not engine_available(name):
        raise FileNotFoundError("Fichier moteur absent : " + name)
    module = importlib.import_module("moteurs." + name.lower())
    if getattr(module, "MOTEUR", None) != name:
        raise RuntimeError("Identité moteur incorrecte")
    if str(getattr(module, "VERSION", "")) != "2.4":
        raise RuntimeError("Version moteur incompatible")
    for attr in ("analyser_course", "verifier_resultat"):
        if not callable(getattr(module, attr, None)):
            raise RuntimeError("Interface moteur absente : " + attr)
    return module


def refuser_doublons(paires):
    resultat = {}
    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError("Clé JSON dupliquée : " + cle)
        resultat[cle] = valeur
    return resultat


def refuser_constante(valeur):
    raise ValueError("Constante JSON interdite : " + valeur)


def load(name):
    """Retourne (objet JSON, erreur), sans écriture."""
    if name not in FICHIERS:
        return [], "Fichier non autorisé"
    path = DATA / name
    fd = None
    try:
        # O_NOFOLLOW évite une substitution du fichier par un lien symbolique.
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if not hasattr(os, "O_NOFOLLOW") and path.is_symlink():
            return [], "Lien symbolique interdit"
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            return [], "Fichier non régulier"
        if info.st_size > MAX_FILE:
            return [], "Fichier trop volumineux : " + name
        with os.fdopen(fd, "rb") as fichier:
            fd = None
            raw = fichier.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            return [], "Fichier trop volumineux : " + name
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=refuser_doublons, parse_constant=refuser_constante)
        if not isinstance(value, (list, dict)):
            return [], "Format JSON invalide : " + name
        return value, None
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
        return [], "Lecture impossible : {} ({})".format(name, type(exc).__name__)
    finally:
        if fd is not None:
            os.close(fd)


def items(value, collection=None):
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    if collection is not None:
        found = value.get(collection)
        return found if isinstance(found, list) else []
    for cle in ("courses", "selections", "items"):
        found = value.get(cle)
        if isinstance(found, list):
            return found
    return []


def verifier_course(course):
    if not isinstance(course, dict):
        return False, "Course invalide"
    try:
        noyau = charger_noyau()
        valide, raison = noyau.verifier_course(copy.deepcopy(course))
        if type(valide) is not bool:
            return False, "Validation non booléenne"
        return valide, str(raison)[:200]
    except Exception as exc:
        return False, "Validation indisponible : " + type(exc).__name__


def course_analysable(course):
    return verifier_course(course)[0]


def verifier_resultat_moteur(name, course, resultat, module=None):
    if name not in MOTEURS or not isinstance(resultat, dict):
        raise ValueError("Résultat moteur invalide")
    if resultat.get("moteur") != name or str(resultat.get("version")) != "2.4":
        raise ValueError("Identité ou version incorrecte")
    statut = resultat.get("statut")
    if statut not in STATUTS:
        raise ValueError("Statut non autorisé")
    if resultat.get("fige") is not False or resultat.get("publication") is not False:
        raise ValueError("FIGÉ ou publication interdits")
    classement, partiel = resultat.get("classement"), resultat.get("classement_partiel")
    if not isinstance(classement, list) or not isinstance(partiel, list):
        raise ValueError("Classements invalides")
    if statut == "ANALYSE_DISPONIBLE":
        if len(classement) != 5 or partiel:
            raise ValueError("Cinq positions obligatoires")
    elif classement or (statut == "NON_ANALYSABLE" and partiel):
        raise ValueError("Classement incompatible avec statut")
    if len(partiel) > 4:
        raise ValueError("Classement partiel trop long")
    if not isinstance(course, dict) or not isinstance(course.get("partants"), list):
        raise ValueError("Partants invalides")
    actifs = set()
    for cheval in course["partants"]:
        if not isinstance(cheval, dict):
            raise ValueError("Partant invalide")
        numero = cheval.get("numero")
        if type(numero) is not int or numero <= 0:
            raise ValueError("Numéro partant invalide")
        if cheval.get("non_partant") is False:
            if numero in actifs:
                raise ValueError("Partant actif dupliqué")
            actifs.add(numero)
    for liste in (classement, partiel):
        numeros = set()
        for rang, cheval in enumerate(liste, 1):
            if not isinstance(cheval, dict):
                raise ValueError("Position invalide")
            numero = cheval.get("numero")
            if type(numero) is not int or numero not in actifs or numero in numeros:
                raise ValueError("Cheval absent, non-partant ou répété")
            if type(cheval.get("position_predite")) is not int or cheval["position_predite"] != rang:
                raise ValueError("Position prédite incohérente")
            numeros.add(numero)
    if module is None:
        module = charger_moteur(name)
    verifier = getattr(module, "verifier_resultat", None)
    if not callable(verifier):
        raise RuntimeError("Vérificateur indisponible")
    reference = copy.deepcopy(resultat)
    verifier(copy.deepcopy(resultat))
    if resultat != reference:
        raise RuntimeError("Résultat modifié pendant vérification")
    json.dumps(resultat, ensure_ascii=False, allow_nan=False)
    return resultat


def resultat_erreur(name, statut, raison):
    return {"moteur": name, "statut": statut, "raison": str(raison)[:200], "classement": [], "classement_partiel": [], "fige": False, "publication": False}


def engine(name, course):
    if name not in MOTEURS:
        return resultat_erreur(name, "INDISPONIBLE", "Moteur inconnu")
    if not engine_available(name):
        return resultat_erreur(name, "INDISPONIBLE", "Fichier absent")
    valide, raison = verifier_course(course)
    if not valide:
        return resultat_erreur(name, "NON_ANALYSABLE", raison)
    try:
        module = charger_moteur(name)
        entree = copy.deepcopy(course)
        reference = copy.deepcopy(entree)
        resultat = module.analyser_course(entree)
        if entree != reference:
            raise RuntimeError("Le moteur a modifié son entrée")
        return verifier_resultat_moteur(name, reference, resultat, module)
    except Exception as exc:
        # Éviter de renvoyer des chemins internes ou données sensibles.
        return resultat_erreur(name, "ERREUR", type(exc).__name__)


def analyser_courses(courses):
    output = []
    for course in items(courses, "courses"):
        if len(output) >= MAX_COURSES_ANALYSEES:
            break
        valide, raison = verifier_course(course)
        if not valide:
            continue
        output.append({"course_id": course.get("id"), "moteurs": {name: engine(name, course) for name in MOTEURS}, "temporaire": True, "fige": False, "publication": False, "raison_validation": raison})
    return output


def diagnostic():
    try:
        noyau = charger_noyau()
        noyau_info = {"disponible": True, "version": getattr(noyau, "VERSION", None), "validation_disponible": callable(getattr(noyau, "verifier_course", None))}
    except Exception as exc:
        noyau_info = {"disponible": False, "erreur": type(exc).__name__}
    moteurs = {}
    for name in MOTEURS:
        info = {"present": engine_available(name), "charge": False, "version": None, "erreur": None}
        if info["present"]:
            try:
                module = charger_moteur(name)
                info.update(charge=True, version=module.VERSION)
            except Exception as exc:
                info["erreur"] = type(exc).__name__
        moteurs[name] = info
    return {"mode": "LECTURE_SEULE_WEB", "version_api": "2.4", "noyau": noyau_info, "moteurs": moteurs, "data_dir_configure": DATA.is_dir(), "origine_autorisee": bool(ORIGIN), "collecte_automatique": False, "publication": False, "figes_automatiques": False}


class Handler(BaseHTTPRequestHandler):
    server_version = "X1000-API/2.4"
    protocol_version = "HTTP/1.1"
    timeout = 10

    def setup(self):
        super().setup()
        self.connection.settimeout(self.timeout)

    def send_json(self, value, status=200, head=False):
        try:
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            status, body = 500, b'{"erreur":"Serialization JSON impossible"}'
        self.send_response(status)
        for cle, valeur in (("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", "default-src 'none'"), ("Content-Length", str(len(body)))):
            self.send_header(cle, valeur)
        if ORIGIN and self.headers.get("Origin", "") == ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Vary", "Origin")
        self.end_headers()
        if not head:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass

    def _read(self, head=False):
        path = urlsplit(self.path).path
        if path not in ROUTES:
            return self.send_json({"erreur": "Route inconnue"}, 404, head)
        if path == "/api/diagnostic":
            return self.send_json(diagnostic(), head=head)
        if path == "/api/status":
            return self.send_json({"mode": "LECTURE_SEULE_WEB", "version": "2.4", "date_utc": datetime.now(timezone.utc).isoformat(), "moteurs": {name: engine_available(name) for name in MOTEURS}, "collecte_automatique": False, "publication": False, "figes_automatiques": False}, head=head)
        donnees, erreur = load(ROUTE_FILES[path])
        if erreur:
            return self.send_json({"erreur": erreur}, 503, head)
        return self.send_json(donnees, head=head)

    def do_GET(self):
        return self._read()

    def do_HEAD(self):
        return self._read(head=True)

    def methode_interdite(self):
        self.close_connection = True
        self.send_header_dummy = None
        return self.send_json({"erreur": "API en lecture seule"}, 405)

    do_POST = methode_interdite
    do_PUT = methode_interdite
    do_PATCH = methode_interdite
    do_DELETE = methode_interdite
    do_OPTIONS = methode_interdite


class APITests(unittest.TestCase):
    def test_json_doublons(self):
        with self.assertRaises(ValueError):
            json.loads('{"a":1,"a":2}', object_pairs_hook=refuser_doublons)

    def test_json_nan(self):
        with self.assertRaises(ValueError):
            json.loads('{"x":NaN}', parse_constant=refuser_constante)

    def test_fichier_non_autorise(self):
        self.assertIsNotNone(load("../secret.json")[1])

    def test_fichier_json_valide_et_invalide(self):
        global DATA
        ancienne = DATA
        try:
            with tempfile.TemporaryDirectory() as dossier:
                DATA = Path(dossier)
                fichier = DATA / "courses.json"
                fichier.write_text('[{"id":"test"}]', encoding="utf-8")
                self.assertEqual(load("courses.json")[0][0]["id"], "test")
                fichier.write_text('{"x":1,"x":2}', encoding="utf-8")
                self.assertIsNotNone(load("courses.json")[1])
                fichier.write_text('NaN', encoding="utf-8")
                self.assertIsNotNone(load("courses.json")[1])
                fichier.write_bytes(b"x" * (MAX_FILE + 1))
                self.assertIsNotNone(load("courses.json")[1])
        finally:
            DATA = ancienne

    def test_liens_symboliques(self):
        global DATA
        ancienne = DATA
        try:
            with tempfile.TemporaryDirectory() as dossier:
                DATA = Path(dossier)
                cible = DATA / "cible.json"
                cible.write_text("[]", encoding="utf-8")
                try:
                    (DATA / "courses.json").symlink_to(cible)
                except (OSError, NotImplementedError):
                    self.skipTest("Liens symboliques indisponibles")
                self.assertIsNotNone(load("courses.json")[1])
        finally:
            DATA = ancienne

    def test_classement_invalide(self):
        course = {"partants": [{"numero": i, "non_partant": False} for i in range(1, 6)]}
        resultat = {"moteur": "M1", "version": "2.4", "statut": "ANALYSE_DISPONIBLE", "fige": False, "publication": False, "classement": [{"numero": 1, "position_predite": i} for i in range(1, 6)], "classement_partiel": []}
        with self.assertRaises(ValueError):
            verifier_resultat_moteur("M1", course, resultat, module=mock.Mock())

    def test_routes_et_methodes(self):
        serveur = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        fil = threading.Thread(target=serveur.serve_forever, daemon=True)
        fil.start()
        try:
            for route in ("/api/status", "/api/diagnostic"):
                connexion = HTTPConnection("127.0.0.1", serveur.server_port, timeout=3)
                connexion.request("GET", route)
                reponse = connexion.getresponse()
                self.assertEqual(reponse.status, 200)
                self.assertIsInstance(json.loads(reponse.read()), dict)
                connexion.close()
            for methode in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                connexion = HTTPConnection("127.0.0.1", serveur.server_port, timeout=3)
                connexion.request(methode, "/api/status")
                reponse = connexion.getresponse()
                self.assertEqual(reponse.status, 405)
                reponse.read()
                connexion.close()
            connexion = HTTPConnection("127.0.0.1", serveur.server_port, timeout=3)
            connexion.request("GET", "/inconnue")
            self.assertEqual(connexion.getresponse().status, 404)
            connexion.close()
        finally:
            serveur.shutdown()
            serveur.server_close()
            fil.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description="X1000 V2.4 - API lecture seule")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--self-test", action="store_true", help="Tests locaux sans démarrer l'API")
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(APITests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if not 1 <= args.port <= 65535:
        parser.error("Port invalide")
    try:
        serveur = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print("Erreur de démarrage : " + str(exc), file=sys.stderr)
        return 1
    print("X1000 PHOENIX V2.4 — API LECTURE SEULE", flush=True)
    print("Adresse : http://{}:{}".format(args.host, args.port), flush=True)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
