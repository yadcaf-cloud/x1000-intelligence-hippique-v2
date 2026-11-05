#!/usr/bin/env python3
# X1000 - Recherche controlee des courses francaises
# Aucun FIGE, aucune publication, aucune archive modifiee.

import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MOTEURS = ("m1", "m2", "m3", "m4", "m5")
BRANCHE = "fix/x1000-v2-reparation-controlee"


def exiger(condition, message):
    if not condition:
        raise RuntimeError(message)


def securite():
    for cle in (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    ):
        exiger(os.getenv(cle) == "1", cle + " obligatoire")

    exiger(
        os.getenv("GITHUB_REF_NAME", BRANCHE) == BRANCHE,
        "Branche non autorisee",
    )


def date_iso(valeur):
    exiger(isinstance(valeur, str), "Date absente")
    date = datetime.fromisoformat(
        valeur.replace("Z", "+00:00")
    )
    exiger(
        date.tzinfo is not None,
        "Fuseau horaire absent",
    )
    return date


def recuperer_courses():
    url = os.getenv("X1000_SOURCE_URL", "").strip()
    domaine = os.getenv(
        "X1000_SOURCE_HOST", ""
    ).strip().lower()

    exiger(url and domaine, "Source non configuree")

    adresse = urlparse(url)

    exiger(
        adresse.scheme == "https"
        and adresse.hostname == domaine
        and not adresse.username
        and not adresse.password
        and adresse.port in (None, 443),
        "Source HTTPS non autorisee",
    )

    # Pas de redirection vers un autre domaine.
    from urllib.request import (
        build_opener,
        HTTPRedirectHandler,
    )

    class SansRedirection(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("Redirection interdite")

    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-ReadOnly/1.0",
        },
    )

    ouvreur = build_opener(SansRedirection)

    with ouvreur.open(requete, timeout=15) as reponse:
        exiger(
            reponse.status == 200,
            "Source indisponible",
        )
        exiger(
            "application/json" in
            reponse.headers.get("Content-Type", ""),
            "Reponse non JSON",
        )
        contenu = reponse.read(2_000_001)

    exiger(
        len(contenu) <= 2_000_000,
        "Reponse trop volumineuse",
    )

    donnees = json.loads(contenu.decode("utf-8"))
    exiger(
        isinstance(donnees, dict)
        and isinstance(donnees.get("courses"), list),
        "Format attendu : objet avec liste courses",
    )

    return donnees["courses"]


def verifier_course(course):
    if not isinstance(course, dict):
        return False, "Format incorrect"

    identifiant = course.get("id", "")

    if not isinstance(identifiant, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}-R\d+-C\d+",
        identifiant,
    ):
        return False, "Identifiant incorrect"

    if course.get("localisation_france_verifiee") is not True:
        return False, "France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    try:
        depart = date_iso(course.get("depart"))
    except (ValueError, RuntimeError, TypeError):
        return False, "Date invalide"

    if depart <= datetime.now(timezone.utc):
        return False, "Depart passe"

    if identifiant[:10] != depart.date().isoformat():
        return False, "Date et identifiant incoherents"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Partants absents"

    actifs = []
    numeros = set()

    for cheval in partants:
        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros
        ):
            return False, "Numero invalide"

        numeros.add(numero)

        if not isinstance(cheval.get("nom"), str):
            return False, "Nom absent"

        if type(cheval.get("non_partant")) is not bool:
            return False, "Statut NP absent"

        if not cheval["non_partant"]:
            actifs.append(cheval)

    if len(actifs) < 5:
        return False, "Moins de cinq actifs"

    return True, "Course structurellement admissible"


def analyser(course):
    # Import du module de tests existant.
    from tests.test_fonctionnel_reel_m1_m5 import (
        protection,
        tester_moteurs,
    )

    from tests.valider_donnees_reelles import (
        valider,
    )

    # Les donnees provenant d'une source doivent
    # etre adaptees au contrat JSON de validation
    # et attestees avant l'analyse sportive.
    actifs = {
        cheval["numero"]
        for cheval in course["partants"]
        if not cheval["non_partant"]
    }

    for nom in MOTEURS:
        module = importlib.import_module(
            "moteurs." + nom
        )
        for cheval in course["partants"]:
            if cheval["numero"] not in actifs:
                continue

            notes = cheval.get(module.CHAMP)
            if not isinstance(notes, dict):
                return {
                    "statut": "DONNEES_INSUFFISANTES",
                    "motif": module.MOTEUR,
                }

            for critere in module.POIDS:
                valeur = notes.get(critere)
                if (
                    type(valeur) not in (int, float)
                    or not 0 <= valeur <= 100
                ):
                    return {
                        "statut": "DONNEES_INSUFFISANTES",
                        "motif": module.MOTEUR,
                    }

    with protection():
        resultats = tester_moteurs(course, actifs)

    return {
        "statut": "ANALYSES_EXECUTEES",
        "resultats": resultats,
    }


def main():
    securite()

    courses = recuperer_courses()

    print("X1000 - COURSES RECUES :", len(courses))

    admissibles = 0
    analyses = 0

    for course in courses:
        ok, motif = verifier_course(course)

        if not ok:
            print("REJET :", motif)
            continue

        admissibles += 1

        # L'attestation de provenance est une
        # condition supplementaire obligatoire.
        preuve = course.get("preuve")

        if not isinstance(preuve, dict) or (
            preuve.get("verification_humaine") is not True
        ):
            print(
                "EN ATTENTE DE PREUVE :",
                course["id"],
            )
            continue

        resultat = analyser(course)

        print(
            "COURSE :", course["id"],
            "RESULTAT :", resultat["statut"],
        )

        if resultat["statut"] == "ANALYSES_EXECUTEES":
            analyses += 1

    print("COURSES ADMISSIBLES :", admissibles)
    print("COURSES ANALYSEES :", analyses)
    print("FIGE : INTERDIT")
    print("PUBLICATION : INTERDITE")
    print("ARCHIVES : INCHANGEES")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            "ERREUR X1000 :", erreur,
            file=sys.stderr,
        )
        sys.exit(1)
