#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.5 — Audit ponctuel du programme PMU, sans écriture.

Aucune collecte automatique, aucun FIGÉ, aucune publication, aucune
transmission aux moteurs. Une requête HTTPS n'est lancée qu'avec --audit.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import re
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

VERSION = "2.5"
BASE = "https://online.turfinfo.api.pmu.fr/rest/client/1"
HOTE_AUTORISE = "online.turfinfo.api.pmu.fr"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 15
PARIS = ZoneInfo("Europe/Paris")
MAX_NOEUDS = 100_000
MAX_PROFONDEUR = 60


class RedirectionInterdite(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirection HTTP interdite")


def refuser_doublons(paires):
    resultat = {}
    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(f"Cle JSON dupliquee : {cle}")
        resultat[cle] = valeur
    return resultat


def refuser_constante(valeur):
    raise ValueError(f"Constante JSON interdite : {valeur}")


def verifier_url(url):
    if not isinstance(url, str) or not url or any(ord(c) <= 32 for c in url):
        raise ValueError("URL invalide")
    try:
        parties = urlsplit(url)
        port = parties.port
    except ValueError as exc:
        raise ValueError("URL mal formee") from exc
    if parties.scheme != "https":
        raise ValueError("HTTPS obligatoire")
    if parties.netloc not in (HOTE_AUTORISE, HOTE_AUTORISE + ":443"):
        raise ValueError("Hote ou autorite non autorise")
    if parties.username is not None or parties.password is not None:
        raise ValueError("Identifiants URL interdits")
    if port not in (None, 443):
        raise ValueError("Port non autorise")
    if parties.query or parties.fragment or "?" in url or "#" in url:
        raise ValueError("Parametres URL interdits")
    match = re.fullmatch(r"/rest/client/1/programme/([0-9]{8})", parties.path)
    if not match:
        raise ValueError("Chemin PMU non autorise")
    try:
        datetime.strptime(match.group(1), "%d%m%Y")
    except ValueError as exc:
        raise ValueError("Date PMU invalide") from exc


def verifier_complexite(donnees):
    pile = [(donnees, 0)]
    noeuds = 0
    while pile:
        valeur, profondeur = pile.pop()
        noeuds += 1
        if noeuds > MAX_NOEUDS or profondeur > MAX_PROFONDEUR:
            raise ValueError("JSON trop complexe")
        if isinstance(valeur, dict):
            pile.extend((v, profondeur + 1) for v in valeur.values())
        elif isinstance(valeur, list):
            pile.extend((v, profondeur + 1) for v in valeur)


def decoder_json(contenu):
    if not contenu or len(contenu) > MAX_BYTES:
        raise ValueError("Taille de reponse invalide")
    try:
        texte = contenu.decode("utf-8-sig")
        donnees = json.loads(
            texte,
            object_pairs_hook=refuser_doublons,
            parse_constant=refuser_constante,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("JSON invalide ou trop profond") from exc
    verifier_complexite(donnees)
    return donnees


def recuperer_json(url):
    """Une seule requete GET explicite, aucune persistance."""
    verifier_url(url)
    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "X1000-V2.5-Audit/1.0",
        },
        method="GET",
    )
    # Pas de proxy provenant implicitement des variables d'environnement.
    opener = build_opener(ProxyHandler({}), RedirectionInterdite())
    with opener.open(requete, timeout=TIMEOUT) as reponse:
        if reponse.status != 200:
            raise ValueError(f"Statut HTTP inattendu : {reponse.status}")
        type_media = reponse.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if type_media != "application/json" and not type_media.endswith("+json"):
            raise ValueError("Type de contenu non JSON")
        encodage = reponse.headers.get("Content-Encoding", "identity").strip().lower()
        if encodage not in ("", "identity"):
            raise ValueError("Reponse compressee interdite")
        longueur = reponse.headers.get("Content-Length")
        if longueur is not None:
            if not re.fullmatch(r"[0-9]+", longueur.strip()):
                raise ValueError("Content-Length invalide")
            if int(longueur) > MAX_BYTES:
                raise ValueError("Taille HTTP interdite")
        contenu = reponse.read(MAX_BYTES + 1)
        if longueur is not None and len(contenu) != int(longueur):
            raise ValueError("Content-Length incoherent")
    donnees = decoder_json(contenu)
    return donnees, hashlib.sha256(contenu).hexdigest()


def inspecter_programme(donnees):
    """Validation structurelle uniquement : jamais validation sportive."""
    if not isinstance(donnees, dict):
        raise ValueError("Programme PMU invalide")
    programme = donnees.get("programme", donnees)
    if not isinstance(programme, dict):
        raise ValueError("Objet programme invalide")
    reunions = programme.get("reunions")
    if not isinstance(reunions, list):
        raise ValueError("Structure des reunions inconnue")
    total = 0
    for i, reunion in enumerate(reunions, 1):
        if not isinstance(reunion, dict):
            raise ValueError(f"Reunion {i} invalide")
        courses = reunion.get("courses")
        if not isinstance(courses, list):
            raise ValueError(f"Liste de courses invalide pour reunion {i}")
        for j, course in enumerate(courses, 1):
            if not isinstance(course, dict):
                raise ValueError(f"Course brute invalide : reunion {i}, course {j}")
        total += len(courses)
    return {
        "reunions": len(reunions),
        "courses_brutes": total,
        "courses_france_verifiees": 0,
        "courses_transmises_moteurs": 0,
        "validation_sportive": False,
        "raison": "Localisation France, depart, partants et non-partants non verifies",
    }


def analyser_date(valeur, aujourd_hui):
    if valeur is None:
        return aujourd_hui
    if not isinstance(valeur, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", valeur):
        raise ValueError("Format date attendu : YYYY-MM-DD")
    try:
        jour = date.fromisoformat(valeur)
    except ValueError as exc:
        raise ValueError("Date calendrier invalide") from exc
    if jour != aujourd_hui:
        raise ValueError("Audit limite a la journee courante en heure de Paris")
    return jour


class TestsAudit(unittest.TestCase):
    def test_url_valide(self):
        verifier_url(BASE + "/programme/04112026")

    def test_urls_interdites(self):
        urls = [
            "http://online.turfinfo.api.pmu.fr/rest/client/1/programme/04112026",
            "https://evil.example/rest/client/1/programme/04112026",
            "https://online.turfinfo.api.pmu.fr.evil.example/rest/client/1/programme/04112026",
            "https://online.turfinfo.api.pmu.fr:444/rest/client/1/programme/04112026",
            BASE + "/programme/04112026?x=1",
            BASE + "/programme/31112026",
            BASE + "/programme/04112026#frag",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                verifier_url(url)

    def test_json_doublons(self):
        with self.assertRaises(ValueError):
            decoder_json(b'{"x":1,"x":2}')

    def test_json_nan(self):
        with self.assertRaises(ValueError):
            decoder_json(b'{"x":NaN}')

    def test_json_taille(self):
        with self.assertRaises(ValueError):
            decoder_json(b" " * (MAX_BYTES + 1))

    def test_json_profondeur(self):
        with self.assertRaises(ValueError):
            verifier_complexite([[[0]]] if MAX_PROFONDEUR < 3 else _emboiter(MAX_PROFONDEUR + 1))

    def test_structure(self):
        r = inspecter_programme({"programme": {"reunions": [{"courses": [{}, {}]}]}})
        self.assertEqual(r["courses_brutes"], 2)
        self.assertFalse(r["validation_sportive"])
        self.assertEqual(r["courses_transmises_moteurs"], 0)

    def test_structure_invalide(self):
        with self.assertRaises(ValueError):
            inspecter_programme({"reunions": [{"courses": [None]}]})

    def test_date(self):
        today = date(2026, 11, 4)
        self.assertEqual(analyser_date(None, today), today)
        with self.assertRaises(ValueError):
            analyser_date("2026-11-03", today)
        with self.assertRaises(ValueError):
            analyser_date("2026-02-30", today)

    def test_empreinte(self):
        self.assertEqual(len(hashlib.sha256(b"{}").hexdigest()), 64)

    def test_redirection(self):
        with self.assertRaises(ValueError):
            RedirectionInterdite().redirect_request(None, None, 302, "Found", {}, "https://evil.example")

    def test_aucun_reseau_sans_audit(self):
        with patch(__name__ + ".recuperer_json", side_effect=AssertionError("reseau interdit")):
            self.assertEqual(main([]), 0)



def _emboiter(profondeur):
    valeur = 0
    for _ in range(profondeur):
        valeur = [valeur]
    return valeur


def main(argv=None):
    parser = argparse.ArgumentParser(description="X1000 V2.5 - Audit PMU ponctuel en lecture seule")
    parser.add_argument("--date", help="YYYY-MM-DD (aujourd'hui, heure de Paris uniquement)")
    groupe = parser.add_mutually_exclusive_group()
    groupe.add_argument("--audit", action="store_true", help="Autoriser une requete PMU ponctuelle")
    groupe.add_argument("--self-test", action="store_true", help="Executer les tests sans reseau")
    args = parser.parse_args(argv)
    if args.self_test:
        # Ne pas appeler unittest.main : il analyserait les arguments CLI.
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestsAudit)
        resultat = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if resultat.wasSuccessful() else 1
    if not args.audit:
        parser.print_help()
        return 0
    try:
        jour = analyser_date(args.date, datetime.now(PARIS).date())
        url = f"{BASE}/programme/{jour:%d%m%Y}"
        donnees, empreinte = recuperer_json(url)
        resultat = inspecter_programme(donnees)
        resultat.update({
            "version": VERSION,
            "statut": "AUDIT_SEUL_SANS_PUBLICATION",
            "date": jour.isoformat(),
            "source": url,
            "source_sha256": empreinte,
            "collecte_a": datetime.now(timezone.utc).isoformat(),
            "fige": False,
            "publication": False,
        })
        print(json.dumps(resultat, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, HTTPError, URLError, TimeoutError, UnicodeError) as exc:
        print(f"COLLECTE REFUSEE : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
