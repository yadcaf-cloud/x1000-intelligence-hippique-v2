#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X1000 PHOENIX - ADAPTATEUR PMU JSON
Diagnostic en lecture seule, sans ecriture.
Python 3.11 - bibliotheque standard.

Aucun FIGE, pronostic, commit, push,
deploiement ou changement d'archives.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import (
    Request, build_opener, HTTPRedirectHandler
)
from zoneinfo import ZoneInfo

HOST = "online.turfinfo.api.pmu.fr"
BASE = "https://" + HOST + "/rest/client/1"
MAX_BYTES = 2_000_000
MAX_COURSES = 150
PARIS = ZoneInfo("Europe/Paris")


class SansRedirection(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Redirection interdite")


def exiger(ok, message):
    if not ok:
        raise RuntimeError(message)


def securite():
    for nom in (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    ):
        exiger(
            os.getenv(nom) == "1",
            "Protection absente : " + nom
        )

    branche = os.getenv("GITHUB_REF_NAME")
    if branche:
        exiger(
            branche == "fix/x1000-v2-reparation-controlee",
            "Branche non autorisee"
        )

    depot = os.getenv("GITHUB_REPOSITORY")
    if depot:
        exiger(
            depot == "yadcaf-cloud/x1000-intelligence-hippique-v2",
            "Depot non autorise"
        )


def lire_json(url):
    parsed = urlparse(url)
    exiger(
        parsed.scheme == "https"
        and parsed.hostname == HOST
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment,
        "URL non autorisee"
    )

    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-ReadOnly/2.4"
        }
    )

    with build_opener(SansRedirection).open(
        req, timeout=15
    ) as response:
        exiger(
            response.status == 200,
            "HTTP different de 200"
        )
        exiger(
            "application/json" in response.headers.get(
                "Content-Type", ""
            ).lower(),
            "Reponse non JSON"
        )
        raw = response.read(MAX_BYTES + 1)

    exiger(
        len(raw) <= MAX_BYTES,
        "Reponse trop volumineuse"
    )
    return json.loads(raw.decode("utf-8"))


def liste_reunions(data):
    exiger(isinstance(data, dict), "Programme invalide")

    programme = data.get("programme", data)
    exiger(
        isinstance(programme, dict),
        "Objet programme absent"
    )

    reunions = programme.get("reunions")
    exiger(
        isinstance(reunions, list),
        "Liste reunions absente"
    )
    return reunions


def numero(obj, *cles):
    for cle in cles:
        val = obj.get(cle)
        if type(val) is int and val > 0:
            return val
    return None


def liste_courses(reunion):
    courses = reunion.get("courses")
    exiger(
        isinstance(courses, list),
        "Liste courses absente"
    )
    return courses


def liste_partants(data):
    if isinstance(data, list):
        return data

    exiger(
        isinstance(data, dict),
        "Reponse participants invalide"
    )
    partants = data.get("participants")
    exiger(
        isinstance(partants, list),
        "Liste participants absente"
    )
    return partants


def normaliser_partants(donnees):
    sortie = []
    vus = set()

    for p in liste_partants(donnees):
        exiger(isinstance(p, dict), "Participant invalide")

        n = numero(p, "numPmu", "numero")
        nom = p.get("nom", p.get("nomCheval"))

        exiger(
            n is not None
            and isinstance(nom, str)
            and bool(nom.strip())
            and n not in vus,
            "Participant incomplet ou doublon"
        )
        vus.add(n)

        statut = p.get("nonPartant")
        exiger(
            type(statut) is bool,
            "Statut non-partant absent ou invalide"
        )

        sortie.append({
            "numero": n,
            "nom": nom.strip(),
            "non_partant": statut
        })

    return sortie


def depart_course(course, jour):
    # On refuse de deviner une heure de depart.
    heure = course.get("heureDepart")
    if not isinstance(heure, str):
        return None

    # Cas ISO 8601 avec fuseau explicite.
    try:
        dt = datetime.fromisoformat(
            heure.replace("Z", "+00:00")
        )
        if dt.tzinfo is not None:
            return dt.isoformat()
    except ValueError:
        pass

    # Heure HH:MM ou HH:MM:SS publiee
    # pour la journee francaise demandee.
    if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", heure):
        try:
            dt = datetime.fromisoformat(
                jour + "T" + heure
            ).replace(tzinfo=PARIS)

            # Refuser les heures locales ambigues.
            if dt.replace(fold=1).utcoffset() != \
               dt.replace(fold=0).utcoffset():
                return None

            return dt.isoformat()
        except ValueError:
            return None

    return None


def collecter(jour):
    date_pmu = datetime.strptime(
        jour, "%Y-%m-%d"
    ).strftime("%d%m%Y")

    url = BASE + "/programme/" + date_pmu
    reunions = liste_reunions(lire_json(url))

    resultat = []
    total = 0

    for reunion in reunions:
        exiger(
            isinstance(reunion, dict),
            "Reunion invalide"
        )

        nr = numero(
            reunion, "numOfficiel", "numeroReunion"
        )
        exiger(nr is not None, "Numero reunion absent")

        for course in liste_courses(reunion):
            total += 1
            exiger(
                total <= MAX_COURSES,
                "Trop de courses"
            )
            exiger(
                isinstance(course, dict),
                "Course invalide"
            )

            nc = numero(
                course, "numOrdre", "numeroCourse"
            )
            exiger(nc is not None, "Numero course absent")

            identifiant = f"{jour}-R{nr}-C{nc}"
            chemin = f"/programme/{date_pmu}/R{nr}/C{nc}"
            url_partants = BASE + chemin + "/participants"

            fiche = {
                "id": identifiant,
                "source": url_partants,
                "depart": depart_course(course, jour),
                "partants": [],
                "nombre_partants": 0,
                "non_partants": [],
                "localisation_france_verifiee": False,
                "depart_verifie": False,
                "statut": "DONNEES_A_VERIFIER",
                "motifs": []
            }

            try:
                partants = normaliser_partants(
                    lire_json(url_partants)
                )
                fiche["partants"] = partants
                fiche["nombre_partants"] = sum(
                    not p["non_partant"]
                    for p in partants
                )
                fiche["non_partants"] = [
                    p["numero"] for p in partants
                    if p["non_partant"]
                ]
            except Exception as exc:
                fiche["motifs"].append(
                    "Participants : " + str(exc)
                )

            if not fiche["depart"]:
                fiche["motifs"].append(
                    "Depart non verifie"
                )

            fiche["motifs"].append(
                "Localisation France a confirmer"
            )
            fiche["motifs"].append(
                "Indicateurs M1-M5 non disponibles"
            )

            resultat.append(fiche)

    return resultat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=datetime.now(PARIS).date().isoformat()
    )
    parser.add_argument(
        "--self-test",
        action="store_true"
    )
    args = parser.parse_args()

    securite()

    if args.self_test:
        assert numero({"numPmu": 3}, "numPmu") == 3
        assert numero({"numPmu": True}, "numPmu") is None
        assert liste_reunions({
            "programme": {"reunions": []}
        }) == []
        print("SELF-TEST : OK")
        return 0

    exiger(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date),
        "Date invalide"
    )

    courses = collecter(args.date)

    print(json.dumps({
        "systeme": "X1000 PHOENIX",
        "mode": "DIAGNOSTIC_LECTURE_SEULE",
        "date": args.date,
        "nombre_courses": len(courses),
        "courses": courses,
        "analyses_executees": False,
        "fige_automatique": False,
        "publication_autorisee": False,
        "archives_modifiees": False
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(
            "ERREUR ADAPTATEUR : " + str(exc),
            file=sys.stderr
        )
        sys.exit(1)
