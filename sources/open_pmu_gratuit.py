#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 - Intelligence Hippique V2
Connecteur Open PMU gratuit - Controle historique.

SECURITE :
- Lecture seule
- Aucun FIGE
- Aucune publication
- Aucune modification des archives
- Aucun pronostic automatique
- Aucun moteur M1-M5 execute
"""

import json
import os
import sys
from datetime import date, timedelta
from urllib.parse import urlencode, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

BRANCHE_AUTORISEE = (
    "fix/x1000-v2-reparation-controlee"
)

API_BASE = (
    "https://open-pmu-api.vercel.app/api/arrivees"
)

TAILLE_MAX = 2_000_000
TIMEOUT = 15


def verifier_securite():
    """Verifier toutes les protections X1000."""

    protections = (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    )

    for variable in protections:
        if os.getenv(variable) != "1":
            raise RuntimeError(
                f"Protection absente : {variable}"
            )

    branche = os.getenv(
        "GITHUB_REF_NAME",
        BRANCHE_AUTORISEE,
    )

    if branche != BRANCHE_AUTORISEE:
        raise RuntimeError(
            "Execution interdite sur cette branche"
        )

    print("SECURITE X1000 : OK")
    print("Lecture seule : ACTIVE")
    print("FIGE automatique : INTERDIT")
    print("Publication automatique : INTERDITE")


class InterdireRedirection(HTTPRedirectHandler):
    """Eviter toute redirection non controlee."""

    def redirect_request(self, *args, **kwargs):
        raise RuntimeError(
            "Redirection HTTP interdite"
        )


def rechercher_courses_historiques(jour):
    """Interroger une date historique uniquement."""

    if not isinstance(jour, date):
        raise ValueError("Date incorrecte")

    if jour >= date.today():
        raise ValueError(
            "Seules les dates historiques sont autorisees"
        )

    parametres = urlencode({
        "date": jour.strftime("%m/%d/%Y")
    })

    url = API_BASE + "?" + parametres

    adresse = urlparse(url)

    if (
        adresse.scheme != "https"
        or adresse.hostname
        != "open-pmu-api.vercel.app"
    ):
        raise RuntimeError(
            "Domaine HTTPS non autorise"
        )

    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-ReadOnly/1.0",
        },
    )

    ouvreur = build_opener(
        InterdireRedirection()
    )

    print("Source : Open PMU API")
    print("Date :", jour.isoformat())
    print("Mode : HISTORIQUE UNIQUEMENT")

    with ouvreur.open(
        requete,
        timeout=TIMEOUT,
    ) as reponse:

        if reponse.status != 200:
            raise RuntimeError(
                f"Erreur HTTP : {reponse.status}"
            )

        type_contenu = reponse.headers.get(
            "Content-Type", ""
        ).lower()

        if "json" not in type_contenu:
            raise RuntimeError(
                "La source ne renvoie pas du JSON"
            )

        contenu = reponse.read(
            TAILLE_MAX + 1
        )

        if len(contenu) > TAILLE_MAX:
            raise RuntimeError(
                "Reponse trop volumineuse"
            )

    donnees = json.loads(
        contenu.decode("utf-8")
    )

    if not isinstance(donnees, dict):
        raise RuntimeError(
            "Structure JSON inattendue"
        )

    if donnees.get("error") is not False:
        raise RuntimeError(
            "Reponse API non exploitable"
        )

    courses = donnees.get("message")

    if not isinstance(courses, list):
        raise RuntimeError(
            "Liste des courses absente"
        )

    return courses


def afficher_bilan(courses):
    """Afficher un diagnostic sans ecriture."""

    print()
    print("=" * 48)
    print("X1000 - DIAGNOSTIC SOURCE GRATUITE")
    print("=" * 48)

    print(
        "Nombre d'elements retournes :",
        len(courses),
    )

    print("Type de donnees : HISTORIQUES")
    print("Courses futures : NON VERIFIEES")
    print("M1 : NON EXECUTE")
    print("M2 : NON EXECUTE")
    print("M3 : NON EXECUTE")
    print("M4 : NON EXECUTE")
    print("M5 : NON EXECUTE")

    print()
    print("FIGE : AUCUN")
    print("PUBLICATION : AUCUNE")
    print("ARCHIVES : INCHANGEES")
    print("DEPOT GITHUB : INCHANGE")

    print()
    print("CONTROLE SOURCE : TERMINE")


def main():
    verifier_securite()

    # Une date historique pour le diagnostic.
    jour = date.today() - timedelta(days=7)

    courses = rechercher_courses_historiques(
        jour
    )

    afficher_bilan(courses)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except Exception as erreur:
        print()
        print(
            "ECHEC CONTROLE SOURCE :",
            str(erreur),
            file=sys.stderr,
        )
        sys.exit(1)
