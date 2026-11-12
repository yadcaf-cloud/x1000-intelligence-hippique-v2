#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX V2.4
Recherche controlee des courses PMU en France.

Chaine :
COLLECTE -> VERIFICATION -> SELECTION
-> ANALYSES M1-M5 -> COORDINATION

Garanties :
- Branche de reparation controlee uniquement.
- Source HTTPS explicitement autorisee.
- Aucune redirection HTTP.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucun commit, push ou deploiement.
- Aucune ecriture de fichiers.

Les attestations fournies par une source ne
constituent pas une certification officielle.
"""

import copy
import json
import math
import os
import re
import sys

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from urllib.request import (
    Request,
    HTTPRedirectHandler,
    build_opener,
)
from zoneinfo import ZoneInfo

from integration_x1000 import executer_integration
from validation_moteurs import valider_course
from moteurs import m1, m2, m3, m4, m5


BRANCHE = "fix/x1000-v2-reparation-controlee"

MOTEURS = (m1, m2, m3, m4, m5)

MAX_REPONSE = 2_000_000
TIMEOUT = 15
MAX_AGE_PREUVE = timedelta(minutes=10)

IDENTIFIANT = re.compile(
    r"^\d{4}-\d{2}-\d{2}-R[1-9]\d*-C[1-9]\d*$"
)


def exiger(condition, message):
    if not condition:
        raise RuntimeError(message)


def securite():
    """Controle les protections obligatoires."""

    for cle in (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    ):
        exiger(
            os.getenv(cle) == "1",
            f"Protection obligatoire absente : {cle}",
        )

    branche = os.getenv(
        "GITHUB_HEAD_REF"
    ) or os.getenv(
        "GITHUB_REF_NAME",
        BRANCHE,
    )

    exiger(
        branche == BRANCHE,
        "Branche non autorisee",
    )

    depot = os.getenv("GITHUB_REPOSITORY")

    if depot:
        exiger(
            depot == (
                "yadcaf-cloud/"
                "x1000-intelligence-hippique-v2"
            ),
            "Depot non autorise",
        )

    print("SECURITE X1000 : OK")
    print("LECTURE SEULE : ACTIVE")
    print("FIGE : INTERDIT")
    print("PUBLICATION : INTERDITE")


def date_iso(valeur):
    """Convertit une date ISO avec fuseau."""

    exiger(
        isinstance(valeur, str)
        and bool(valeur.strip()),
        "Date absente",
    )

    try:
        date = datetime.fromisoformat(
            valeur.replace("Z", "+00:00")
        )
    except ValueError as erreur:
        raise RuntimeError(
            "Date ISO invalide"
        ) from erreur

    exiger(
        date.tzinfo is not None
        and date.utcoffset() is not None,
        "Fuseau horaire absent",
    )

    return date.astimezone(timezone.utc)


def configuration_source():
    """Retourne la source HTTPS autorisee."""

    url = os.getenv(
        "X1000_SOURCE_URL", ""
    ).strip()

    domaine = os.getenv(
        "X1000_SOURCE_HOST", ""
    ).strip().lower()

    exiger(
        url and domaine,
        "Source PMU non configuree",
    )

    adresse = urlparse(url)

    exiger(
        adresse.scheme == "https"
        and adresse.hostname == domaine
        and not adresse.username
        and not adresse.password
        and adresse.port in (None, 443)
        and not adresse.fragment,
        "Source HTTPS non autorisee",
    )

    return url, domaine


class SansRedirection(HTTPRedirectHandler):
    """Interdit les redirections."""

    def redirect_request(self, *args, **kwargs):
        raise RuntimeError(
            "Redirection HTTP interdite"
        )


def recuperer_courses():
    """
    Collecte les courses depuis la source
    explicitement configuree.

    Aucun fichier local n'est modifie.
    """

    url, domaine = configuration_source()

    requete = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "X1000-ReadOnly/2.4",
        },
    )

    ouvreur = build_opener(SansRedirection)

    with ouvreur.open(
        requete,
        timeout=TIMEOUT,
    ) as reponse:

        exiger(
            reponse.status == 200,
            "Source indisponible",
        )

        type_contenu = reponse.headers.get(
            "Content-Type", ""
        ).lower()

        exiger(
            "application/json" in type_contenu,
            "Reponse non JSON",
        )

        contenu = reponse.read(
            MAX_REPONSE + 1
        )

    exiger(
        len(contenu) <= MAX_REPONSE,
        "Reponse trop volumineuse",
    )

    donnees = json.loads(
        contenu.decode("utf-8")
    )

    exiger(
        isinstance(donnees, dict)
        and isinstance(
            donnees.get("courses"), list
        ),
        "Format attendu : objet avec liste courses",
    )

    print("SOURCE HTTPS :", domaine)
    print(
        "COURSES RECUES :",
        len(donnees["courses"]),
    )

    return donnees["courses"]


def verifier_provenance(course):
    """
    Controle la provenance declaree et
    la fraicheur de la verification.

    Ne pretend pas effectuer une certification
    officielle independante.
    """

    preuve = course.get("preuve")

    if not isinstance(preuve, dict):
        return False, "Preuve absente"

    url_source, domaine = configuration_source()

    source_url = preuve.get("source_url")
    source_nom = preuve.get("source_nom")

    if (
        not isinstance(source_url, str)
        or source_url != url_source
    ):
        return False, "URL de preuve incoherente"

    if (
        not isinstance(source_nom, str)
        or not source_nom.strip()
    ):
        return False, "Nom de source absent"

    if (
        urlparse(source_url).hostname
        != domaine
    ):
        return False, "Domaine de preuve incorrect"

    try:
        verification = date_iso(
            preuve.get("date_verification")
        )
    except (ValueError, RuntimeError, TypeError):
        return False, "Date de preuve invalide"

    age = (
        datetime.now(timezone.utc)
        - verification
    )

    if not (
        timedelta(0)
        <= age
        <= MAX_AGE_PREUVE
    ):
        return False, "Preuve trop ancienne ou future"

    return True, "Provenance structurelle acceptee"


def verifier_course(course):
    """Selectionne les courses structurellement valides."""

    if not isinstance(course, dict):
        return False, "Course invalide"

    identifiant = course.get("id")

    if (
        not isinstance(identifiant, str)
        or not IDENTIFIANT.fullmatch(identifiant)
    ):
        return False, "Identifiant incorrect"

    if (
        course.get(
            "localisation_france_verifiee"
        ) is not True
    ):
        return False, "France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    try:
        depart = date_iso(course.get("depart"))
    except (ValueError, RuntimeError, TypeError):
        return False, "Date invalide"

    if depart <= datetime.now(timezone.utc):
        return False, "Depart deja passe"

    date_france = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).date().isoformat()

    if identifiant[:10] != date_france:
        return False, "Date francaise incoherente"

    try:
        actifs = valider_course(course)
    except (ValueError, RuntimeError) as erreur:
        return False, str(erreur)

    if len(actifs) < 5:
        return False, "Partants insuffisants"

    return True, "Course admissible"


def verifier_indicateurs(course):
    """
    Verifie les indicateurs sans les inventer.

    Les cinq moteurs doivent disposer de
    donnees exploitables pour cinq actifs
    au minimum.
    """

    actifs = [
        cheval
        for cheval in course["partants"]
        if not cheval["non_partant"]
    ]

    for moteur in MOTEURS:
        complets = 0

        for cheval in actifs:
            notes = cheval.get(
                moteur.CHAMP
            )

            if not isinstance(notes, dict):
                continue

            valide = True

            for critere in moteur.POIDS:
                valeur = notes.get(critere)

                if (
                    type(valeur) not in (int, float)
                    or not math.isfinite(valeur)
                    or not 0 <= valeur <= 100
                ):
                    valide = False
                    break

            if valide:
                complets += 1

        if complets < 5:
            return (
                False,
                f"{moteur.MOTEUR} : "
                "indicateurs insuffisants",
            )

    return True, "Indicateurs suffisants"


def analyser(course):
    """
    Execute M1-M5 independamment et
    coordonne leurs sorties.

    Aucun pronostic n'est modifie.
    """

    original = copy.deepcopy(course)

    resultat = executer_integration(
        copy.deepcopy(course)
    )

    exiger(
        course == original,
        "Course modifiee pendant l'analyse",
    )

    exiger(
        isinstance(resultat, dict),
        "Coordination invalide",
    )

    exiger(
        resultat.get("nombre_moteurs") == 5,
        "Moteurs incomplets",
    )

    exiger(
        set(
            resultat.get(
                "analyses_independantes", {}
            )
        ) == {
            "M1", "M2", "M3", "M4", "M5"
        },
        "Analyses independantes incompletes",
    )

    exiger(
        resultat.get(
            "fige_automatique"
        ) is False,
        "FIGE automatique interdit",
    )

    exiger(
        resultat.get(
            "publication_autorisee"
        ) is False,
        "Publication interdite",
    )

    exiger(
        resultat.get(
            "archives_modifiees"
        ) is False,
        "Archives non protegees",
    )

    statut = (
        "ANALYSES_EXECUTEES"
        if resultat.get(
            "coordination_complete"
        ) is True
        else "ANALYSES_PARTIELLES"
    )

    return {
        "statut": statut,
        "coordination": resultat,
    }


def main():
    """Chaine operationnelle en lecture seule."""

    securite()

    courses = recuperer_courses()

    admissibles = 0
    analysees = 0
    partielles = 0
    rejetees = 0

    for course in courses:
        identifiant = (
            course.get("id", "INCONNU")
            if isinstance(course, dict)
            else "INCONNU"
        )

        ok, motif = verifier_course(course)

        if not ok:
            rejetees += 1
            print("REJET :", identifiant, motif)
            continue

        ok, motif = verifier_provenance(course)

        if not ok:
            rejetees += 1
            print(
                "PROVENANCE REFUSEE :",
                identifiant,
                motif,
            )
            continue

        admissibles += 1

        ok, motif = verifier_indicateurs(course)

        if not ok:
            partielles += 1
            print(
                "DONNEES INSUFFISANTES :",
                identifiant,
                motif,
            )
            continue

        resultat = analyser(course)

        print(
            "COURSE :",
            identifiant,
            "STATUT :",
            resultat["statut"],
        )

        if (
            resultat["statut"]
            == "ANALYSES_EXECUTEES"
        ):
            analysees += 1
        else:
            partielles += 1

    print()
    print("=" * 48)
    print("X1000 PHOENIX - BILAN")
    print("=" * 48)
    print("COURSES RECUES :", len(courses))
    print("COURSES ADMISSIBLES :", admissibles)
    print("ANALYSES COMPLETES :", analysees)
    print("ANALYSES PARTIELLES :", partielles)
    print("COURSES REJETEES :", rejetees)
    print("FIGE : AUCUN")
    print("PUBLICATION : AUCUNE")
    print("ARCHIVES : INCHANGEES")
    print("DEPOT : AUCUNE ECRITURE")
    print("=" * 48)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            "ERREUR X1000 :",
            type(erreur).__name__,
            str(erreur),
            file=sys.stderr,
        )
        sys.exit(1)
