#!/usr/bin/env python3
# X1000 - Connecteur gratuit Open PMU
# Consultation historique uniquement.
# Aucun FIGE, publication ou archivage.

import json
import os
import sys
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://open-pmu-api.vercel.app/api/arrivees"
BRANCHE = "fix/x1000-v2-reparation-controlee"


def verifier_securite():
    for variable in (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    ):
        if os.getenv(variable) != "1":
            raise RuntimeError(
                f"Protection obligatoire : {variable}"
            )

    branche = os.getenv("GITHUB_REF_NAME", BRANCHE)
    if branche != BRANCHE:
        raise RuntimeError("Branche non autorisee")


def rechercher(date_course):
    if not isinstance(date_course, date):
        raise ValueError("Date invalide")

    # Une seule requete, limitee a une date.
    parametres = urlencode({
        "date": date_course.strftime("%m/%d/%Y")
    })
    url = BASE + "?" + parametres

    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-Research/1.0",
        },
    )

    with urlopen(requete, timeout=15) as reponse:
        if reponse.status != 200:
            raise RuntimeError("HTTP non valide")

        contenu = reponse.read(2_000_001)

        if len(contenu) > 2_000_000:
            raise RuntimeError("Reponse trop grande")

    donnees = json.loads(
        contenu.decode("utf-8")
    )

    if not isinstance(donnees, dict):
        raise RuntimeError("Format JSON incorrect")

    if donnees.get("error") is not False:
        raise RuntimeError(
            "API : aucune reponse exploitable"
        )

    courses = donnees.get("message")

    if not isinstance(courses, list):
        raise RuntimeError(
            "Liste des courses absente"
        )

    return courses


def main():
    verifier_securite()

    # Controle historique, sans anticipation.
    jour = date.today() - timedelta(days=7)

    print("X1000 - CONTROLE SOURCE GRATUITE")
    print("Date historique :", jour.isoformat())

    courses = rechercher(jour)

    print("Courses retournees :", len(courses))
    print("Nature : DONNEES HISTORIQUES")
    print("Analyse prospective : NON EXECUTEE")
    print("M1-M5 : NON EXECUTES")
    print("FIGE : INTERDIT")
    print("PUBLICATION : INTERDITE")
    print("ARCHIVES : INCHANGEES")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            "ECHEC CONTROLE SOURCE :",
            str(erreur),
            file=sys.stderr,
        )
        sys.exit(1)
