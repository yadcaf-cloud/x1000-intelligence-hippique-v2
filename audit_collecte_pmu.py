#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - AUDIT DE COLLECTE PMU REELLE

Audit technique en lecture seule.

Garanties :
- Source PMU HTTPS autorisee uniquement.
- Aucune donnee inventee.
- Aucune prediction ni FIGE.
- Aucune publication.
- Aucune modification des archives.
- Aucune transmission aux moteurs M1-M5.
- Rejet des JSON invalides ou ambigus.
- Verification structurelle des reunions.
- Empreinte SHA-256 des octets recus.

ATTENTION :
Les courses brutes ne sont jamais des
courses sportivement validees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)
from zoneinfo import ZoneInfo


VERSION = "2.4"

BASE = (
    "https://online.turfinfo.api.pmu.fr"
    "/rest/client/1"
)

HOTE_AUTORISE = "online.turfinfo.api.pmu.fr"

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 15

PARIS = ZoneInfo("Europe/Paris")


class RedirectionInterdite(HTTPRedirectHandler):
    """Bloque toutes les redirections HTTP."""

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        raise ValueError(
            "Redirection HTTP interdite"
        )


def refuser_doublons(paires):
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(
                f"Cle JSON dupliquee : {cle}"
            )

        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur):
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def verifier_url(url):
    """Controle strict de la source PMU."""

    parties = urlsplit(url)

    if parties.scheme != "https":
        raise ValueError(
            "HTTPS obligatoire"
        )

    if parties.hostname != HOTE_AUTORISE:
        raise ValueError(
            "Hote PMU non autorise"
        )

    if parties.username or parties.password:
        raise ValueError(
            "Identifiants URL interdits"
        )

    if parties.port not in (None, 443):
        raise ValueError(
            "Port non autorise"
        )

    if parties.query or parties.fragment:
        raise ValueError(
            "Parametres URL interdits"
        )

    chemin_attendu = re.fullmatch(
        r"/rest/client/1/programme/\d{8}",
        parties.path,
    )

    if chemin_attendu is None:
        raise ValueError(
            "Chemin PMU non autorise"
        )


def recuperer_json(url):
    """Recupere les donnees sans les enregistrer."""

    verifier_url(url)

    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-V2.4-Audit/1.0",
        },
        method="GET",
    )

    opener = build_opener(
        RedirectionInterdite()
    )

    with opener.open(
        requete,
        timeout=TIMEOUT,
    ) as reponse:

        if reponse.status != 200:
            raise ValueError(
                f"Erreur HTTP : {reponse.status}"
            )

        type_contenu = reponse.headers.get(
            "Content-Type", ""
        )

        type_media = (
            type_contenu.split(";", 1)[0]
            .strip()
            .lower()
        )

        if not (
            type_media == "application/json"
            or type_media.endswith("+json")
        ):
            raise ValueError(
                "Type de contenu non JSON"
            )

        longueur = reponse.headers.get(
            "Content-Length"
        )

        if longueur is not None:
            try:
                taille_annoncee = int(longueur)
            except ValueError as erreur:
                raise ValueError(
                    "Content-Length invalide"
                ) from erreur

            if (
                taille_annoncee < 0
                or taille_annoncee > MAX_BYTES
            ):
                raise ValueError(
                    "Taille HTTP interdite"
                )

        contenu = reponse.read(
            MAX_BYTES + 1
        )

    if len(contenu) > MAX_BYTES:
        raise ValueError(
            "Reponse trop volumineuse"
        )

    if not contenu:
        raise ValueError(
            "Reponse PMU vide"
        )

    empreinte = hashlib.sha256(
        contenu
    ).hexdigest()

    donnees = json.loads(
        contenu.decode("utf-8-sig"),
        object_pairs_hook=refuser_doublons,
        parse_constant=refuser_constante,
    )

    return donnees, empreinte


def inspecter_programme(donnees):
    """
    Audit structurel uniquement.

    Ne valide pas :
    - Le pays de la reunion.
    - Le depart reel.
    - La liste officielle des partants.
    - Les non-partants.
    - Les performances sportives.
    """

    if not isinstance(donnees, dict):
        raise ValueError(
            "Programme PMU invalide"
        )

    if "programme" in donnees:
        programme = donnees["programme"]

        if not isinstance(programme, dict):
            raise ValueError(
                "Objet programme invalide"
            )

        reunions = programme.get("reunions")

    else:
        reunions = donnees.get("reunions")

    if not isinstance(reunions, list):
        raise ValueError(
            "Structure des reunions inconnue"
        )

    nombre_courses = 0

    for indice_reunion, reunion in enumerate(
        reunions, start=1
    ):
        if not isinstance(reunion, dict):
            raise ValueError(
                f"Reunion {indice_reunion} invalide"
            )

        courses = reunion.get("courses")

        if not isinstance(courses, list):
            raise ValueError(
                "Liste de courses invalide "
                f"pour reunion {indice_reunion}"
            )

        for indice_course, course in enumerate(
            courses, start=1
        ):
            if not isinstance(course, dict):
                raise ValueError(
                    "Course brute invalide : "
                    f"reunion {indice_reunion}, "
                    f"course {indice_course}"
                )

        nombre_courses += len(courses)

    return {
        "reunions": len(reunions),
        "courses_brutes": nombre_courses,
        "courses_france_verifiees": 0,
        "courses_transmises_moteurs": 0,
        "validation_sportive": False,
        "raison": (
            "Localisation France, depart, "
            "partants et non-partants "
            "non encore verifies"
        ),
    }


def analyser_date(valeur, aujourd_hui):
    """Accepte uniquement la date courante Paris."""

    if valeur is None:
        return aujourd_hui

    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        valeur,
    ):
        raise ValueError(
            "Format date attendu : YYYY-MM-DD"
        )

    try:
        jour = datetime.strptime(
            valeur,
            "%Y-%m-%d",
        ).date()
    except ValueError as erreur:
        raise ValueError(
            "Date calendrier invalide"
        ) from erreur

    if jour != aujourd_hui:
        raise ValueError(
            "Audit limite a la journee "
            "courante en heure de Paris"
        )

    return jour


def main():
    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 - Audit PMU reel "
            "sans publication"
        )
    )

    parser.add_argument(
        "--date",
        help=(
            "Date YYYY-MM-DD, "
            "aujourd'hui a Paris par defaut"
        ),
    )

    arguments = parser.parse_args()

    try:
        maintenant_paris = datetime.now(PARIS)

        jour = analyser_date(
            arguments.date,
            maintenant_paris.date(),
        )

        date_pmu = jour.strftime("%d%m%Y")

        url = f"{BASE}/programme/{date_pmu}"

        donnees, empreinte = recuperer_json(
            url
        )

        resultat = inspecter_programme(
            donnees
        )

        resultat.update({
            "version": VERSION,
            "statut": "AUDIT_SEUL_SANS_PUBLICATION",
            "date": jour.isoformat(),
            "source": url,
            "source_sha256": empreinte,
            "collecte_a": datetime.now(
                timezone.utc
            ).isoformat(),
            "fige": False,
            "publication": False,
        })

        print(
            json.dumps(
                resultat,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )

        return 0

    except (
        ValueError,
        OSError,
        HTTPError,
        URLError,
        TimeoutError,
        UnicodeError,
    ) as erreur:

        print(
            f"COLLECTE REFUSEE : {erreur}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
