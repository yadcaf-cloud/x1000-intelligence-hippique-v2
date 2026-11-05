#!/usr/bin/env python3
"""X1000 - Diagnostic M1-M5, sans ecriture ni reseau."""

import builtins
import copy
import importlib
import json
import os
import socket
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "fix/x1000-v2-reparation-controlee"
MOTEURS = ("M1", "M2", "M3", "M4", "M5")
FIXTURES = ROOT / "tests" / "donnees_reelles"

sys.path.insert(0, str(ROOT))


def exiger(condition, message):
    if not condition:
        raise AssertionError(message)


@contextmanager
def protection():
    """Interdit les ecritures Python et connexions reseau."""
    original_open = builtins.open
    original_io_open = __import__("io").open
    original_os_open = os.open

    def open_protege(file, mode="r", *args, **kwargs):
        if any(c in str(mode) for c in "wax+"):
            raise PermissionError("Ecriture interdite")
        return original_open(file, mode, *args, **kwargs)

    def os_open_protege(file, flags, *args, **kwargs):
        interdits = (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT
            | os.O_TRUNC | os.O_APPEND
        )
        if flags & interdits:
            raise PermissionError("Ecriture interdite")
        return original_os_open(file, flags, *args, **kwargs)

    def interdit(*args, **kwargs):
        raise PermissionError("Operation interdite")

    with patch("builtins.open", open_protege), \
         patch("io.open", open_protege), \
         patch("os.open", os_open_protege), \
         patch("socket.socket.connect", interdit), \
         patch("socket.socket.connect_ex", interdit), \
         patch("socket.create_connection", interdit), \
         patch("os.remove", interdit), \
         patch("os.unlink", interdit), \
         patch("os.rename", interdit), \
         patch("os.replace", interdit), \
         patch("os.mkdir", interdit), \
         patch("os.makedirs", interdit):
        yield


def charger_fixture(chemin):
    with chemin.open("r", encoding="utf-8") as fichier:
        donnees = json.load(fichier)

    exiger(isinstance(donnees, dict),
           "Fixture invalide")

    preuve = donnees.get("preuve")
    course = donnees.get("course")

    exiger(isinstance(preuve, dict),
           "Preuve absente")
    exiger(isinstance(course, dict),
           "Course absente")

    champs = (
        "source_url",
        "source_nom",
        "date_verification",
    )
    for champ in champs:
        exiger(isinstance(preuve.get(champ), str)
               and preuve[champ].strip(),
               "Preuve incomplete : " + champ)

    exiger(
        preuve["source_url"].startswith("https://"),
        "Source HTTPS obligatoire"
    )
    exiger(
        preuve.get("verification_humaine") is True,
        "Verification humaine non attestee"
    )

    exiger(
        course.get("localisation_france_verifiee") is True,
        "Localisation francaise non attestee"
    )
    exiger(
        course.get("depart_verifie") is True,
        "Depart non atteste"
    )

    partants = course.get("partants")
    exiger(isinstance(partants, list) and partants,
           "Liste des partants absente")

    numeros = []
    actifs = set()

    for cheval in partants:
        exiger(isinstance(cheval, dict),
               "Partant invalide")
        n = cheval.get("numero")
        exiger(type(n) is int and n > 0,
               "Numero invalide")
        exiger(isinstance(cheval.get("nom"), str)
               and cheval["nom"].strip(),
               "Nom de cheval manquant")
        exiger(type(cheval.get("non_partant")) is bool,
               "Statut non-partant absent")
        numeros.append(n)
        if not cheval["non_partant"]:
            actifs.add(n)

    exiger(len(numeros) == len(set(numeros)),
           "Numeros en double")
    exiger(len(actifs) >= 5,
           "Moins de cinq partants actifs")

    return course, actifs


def verifier_sortie(sortie, moteur, actifs):
    exiger(isinstance(sortie, dict),
           moteur + " : sortie non JSON")
    exiger(sortie.get("moteur") == moteur,
           moteur + " : identite incorrecte")
    exiger(sortie.get("fige") is False,
           moteur + " : FIGE interdit")
    exiger(sortie.get("publication") is False,
           moteur + " : publication interdite")

    statut = sortie.get("statut")
    exiger(statut in (
        "ANALYSE_DISPONIBLE",
        "DONNEES_INSUFFISANTES",
        "NON_ANALYSABLE",
    ), moteur + " : statut invalide")

    classement = sortie.get("classement", [])
    partiel = sortie.get("classement_partiel", [])

    exiger(isinstance(classement, list),
           "Classement invalide")
    exiger(isinstance(partiel, list),
           "Classement partiel invalide")

    numeros = []

    for cheval in classement + partiel:
        exiger(isinstance(cheval, dict),
               "Position invalide")
        numero = cheval.get("numero")
        exiger(type(numero) is int,
               "Numero de classement invalide")
        exiger(numero in actifs,
               "Non-partant ou inconnu classe")
        numeros.append(numero)

    exiger(len(numeros) == len(set(numeros)),
           "Doublon dans les classements")
    exiger(len(classement) <= 5,
           "Plus de cinq positions")

    if statut == "ANALYSE_DISPONIBLE":
        exiger(len(classement) == 5,
               "Classement complet attendu")
    else:
        exiger(not classement,
               "Classement complet non justifie")

    return statut, numeros


def tester_moteurs(course=None, actifs=None):
    resultats = {}

    for nom in MOTEURS:
        module = importlib.import_module(
            "moteurs." + nom.lower()
        )

        exiger(module.MOTEUR == nom,
               "Identite moteur incorrecte")

        module.verifier_noyau()
        exiger(module.self_test() is True,
               nom + " : autotest echoue")

        print(nom, "- configuration et autotest OK")

        if course is None:
            continue

        entree = copy.deepcopy(course)
        reference = copy.deepcopy(entree)

        sortie = module.analyser_course(entree)

        exiger(entree == reference,
               nom + " : entree modifiee")

        module.noyau_commun.verifier_sortie_analyse(
            sortie, course
        )

        statut, numeros = verifier_sortie(
            sortie, nom, actifs
        )

        resultats[nom] = {
            "statut": statut,
            "numeros": numeros,
        }

        print(nom, "-", statut, numeros)

    return resultats


def main():
    exiger(os.getenv("X1000_READ_ONLY") == "1",
           "Mode lecture seule obligatoire")
    exiger(os.getenv("X1000_NO_FIGE") == "1",
           "Protection FIGE absente")
    exiger(os.getenv("X1000_NO_PUBLICATION") == "1",
           "Protection publication absente")

    exiger(os.getenv("GITHUB_REF_NAME", BRANCH) == BRANCH,
           "Branche incorrecte")

    # Isolation du repertoire courant hors depot.
    with tempfile.TemporaryDirectory() as dossier:
        os.chdir(dossier)

        with protection():
            resultats = tester_moteurs()

            fichiers = sorted(
                FIXTURES.glob("*.json")
            ) if FIXTURES.exists() else []

            if not fichiers:
                print(
                    "COURSES REELLES : NON TESTEES "
                    "(aucune fixture attestee)"
                )
                return 0

            for fichier in fichiers:
                print("COURSE :", fichier.name)
                course, actifs = charger_fixture(fichier)
                resultats = tester_moteurs(
                    course, actifs
                )

                exiger(
                    set(resultats) == set(MOTEURS),
                    "Moteurs incomplets"
                )

            print("TESTS TERMINES - LECTURE SEULE")
            print(
                "Les attestations de source doivent "
                "etre controlees independamment."
            )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            "ECHEC X1000 :",
            type(erreur).__name__,
            str(erreur),
            file=sys.stderr
        )
        sys.exit(1)
