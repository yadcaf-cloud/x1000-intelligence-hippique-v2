#!/usr/bin/env python3
# X1000 PHOENIX V2 - SOURCES OFFICIELLES
# Lecture seule - Aucun FIGE, archive ou pronostic modifie
# Python 3.11+ - Aucune dependance externe

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser

TIMEOUT = 12
MAX_BYTES = 3_000_000

SOURCES = [
    {
        "nom": "PMU - Programme date",
        "url": lambda d: (
            "https://www.pmu.fr/turf/"
            + d.strftime("%d%m%Y") + "/"
        ),
        "type": "programme",
    },
    {
        "nom": "PMU - Turf",
        "url": lambda d: "https://www.pmu.fr/turf/",
        "type": "programme",
    },
    {
        "nom": "PMU - Point de vente",
        "url": lambda d: "https://www.pmu.fr/point-de-vente/",
        "type": "programme",
    },
    {
        "nom": "France Galop - Officiel",
        "url": lambda d: "https://www.france-galop.com/fr",
        "type": "institution",
    },
    {
        "nom": "LeTROT - Officiel",
        "url": lambda d: "https://www.letrot.com/",
        "type": "institution",
    },
]


class ExtracteurTexte(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parties = []
        self.ignorer = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignorer += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignorer:
            self.ignorer -= 1

    def handle_data(self, data):
        if not self.ignorer:
            self.parties.append(data)

    def texte(self):
        return re.sub(
            r"\s+", " ", unescape(" ".join(self.parties))
        ).strip()


def telecharger(url):
    requete = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 X1000-PHOENIX-ReadOnly",
            "Accept": "text/html,application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        requete, timeout=TIMEOUT
    ) as reponse:
        statut = reponse.status
        type_contenu = reponse.headers.get(
            "Content-Type", ""
        ).lower()
        contenu = reponse.read(MAX_BYTES + 1)

        if len(contenu) > MAX_BYTES:
            raise ValueError("Reponse trop volumineuse")

        return statut, type_contenu, contenu


def analyser(statut, type_contenu, contenu, categorie):
    resultat = {
        "accessible": False,
        "programme_valide": False,
        "courses_detectees": 0,
        "motif": "",
    }

    if statut != 200:
        resultat["motif"] = "HTTP " + str(statut)
        return resultat

    if not contenu:
        resultat["motif"] = "Reponse vide"
        return resultat

    if "json" in type_contenu:
        try:
            json.loads(contenu.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            resultat["motif"] = "JSON invalide"
            return resultat

        resultat["accessible"] = True
        resultat["motif"] = (
            "JSON lisible, schema metier non valide"
        )
        return resultat

    if "html" not in type_contenu:
        resultat["motif"] = "Format non reconnu"
        return resultat

    decode = contenu.decode("utf-8", errors="replace")
    parseur = ExtracteurTexte()
    parseur.feed(decode)
    texte = parseur.texte()

    if len(texte) < 80:
        resultat["motif"] = "Contenu insuffisant"
        return resultat

    resultat["accessible"] = True

    if categorie != "programme":
        resultat["motif"] = (
            "Site officiel accessible, pas de flux valide"
        )
        return resultat

    # Detection indicative uniquement.
    # Ne constitue PAS une validation des partants.
    reunions = re.findall(r"\bR\d{1,2}\b", texte, re.I)
    courses = re.findall(r"\bC\d{1,2}\b", texte, re.I)
    vocabulaire = bool(
        re.search(
            r"\b(courses|reunions|partants)\b",
            texte,
            re.I,
        )
    )

    resultat["courses_detectees"] = min(
        len(reunions), len(courses)
    )

    if reunions and courses and vocabulaire:
        resultat["motif"] = (
            "Programme apparent, donnees non structurees"
        )
    else:
        resultat["motif"] = (
            "Page accessible, programme non confirme"
        )

    return resultat


def verifier_source(source, jour):
    url = source["url"](jour)

    resultat = {
        "source": source["nom"],
        "url": url,
        "accessible": False,
        "programme_valide": False,
        "courses_detectees": 0,
        "motif": "",
    }

    try:
        statut, type_contenu, contenu = telecharger(url)
        resultat.update(
            analyser(
                statut,
                type_contenu,
                contenu,
                source["type"],
            )
        )
    except urllib.error.HTTPError as erreur:
        resultat["motif"] = f"HTTP {erreur.code}"
    except urllib.error.URLError as erreur:
        resultat["motif"] = (
            f"Erreur reseau: {erreur.reason}"
        )
    except Exception as erreur:
        resultat["motif"] = (
            f"{type(erreur).__name__}: {erreur}"
        )

    return resultat


def self_test():
    assert len(SOURCES) == 5
    assert len({
        source["nom"] for source in SOURCES
    }) == 5

    assert not analyser(
        200, "text/html", b"", "programme"
    )["accessible"]

    assert not analyser(
        200, "application/json",
        b'{"reunions":[]}', "programme"
    )["programme_valide"]

    assert not analyser(
        403, "text/html", b"interdit", "programme"
    )["accessible"]

    assert not analyser(
        200, "text/html",
        b"<html><body>Bonjour</body></html>",
        "programme",
    )["programme_valide"]

    print("SELF-TEST OK : controles locaux valides")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--self-test", action="store_true"
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date YYYY-MM-DD",
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    # Ces protections sont obligatoires.
    protections = (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    )

    for nom in protections:
        if os.environ.get(nom) != "1":
            print(f"SECURITE : {nom}=1 obligatoire")
            return 2

    try:
        jour = date.fromisoformat(args.date)
    except ValueError:
        print("Date invalide")
        return 2

    print("=== X1000 PHOENIX - SOURCES ===")
    print("Date :", jour.isoformat())
    print("Mode : LECTURE SEULE")
    print("FIGES : PROTEGES")
    print("PUBLICATION : DESACTIVEE")
    print()

    resultats = []
    premiere_accessible = None
    premiere_valide = None

    for source in SOURCES:
        resultat = verifier_source(source, jour)
        resultats.append(resultat)

        print("SOURCE :", resultat["source"])
        print("URL :", resultat["url"])
        print("ETAT :", resultat["motif"])
        print()

        if resultat["accessible"] and not premiere_accessible:
            premiere_accessible = resultat

        if (
            resultat["programme_valide"]
            and premiere_valide is None
        ):
            premiere_valide = resultat

    print("=== BILAN ===")

    if premiere_accessible:
        print(
            "Premiere source accessible :",
            premiere_accessible["source"],
        )
    else:
        print("Aucune source accessible")

    if premiere_valide:
        print(
            "Source de donnees valide :",
            premiere_valide["source"],
        )
        return 0

    print("AUCUN FLUX METIER VALIDE")
    print("Aucune donnee transmise aux moteurs M1-M5")
    print("Aucun FIGE ni pronostic modifie")

    # Diagnostic accessible, mais integration bloquee.
    return 3


if __name__ == "__main__":
    sys.exit(main())
