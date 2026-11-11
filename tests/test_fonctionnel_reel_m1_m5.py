#!/usr/bin/env python3
"""X1000 PHOENIX - Diagnostic controle M1-M5, sans reseau."""

import builtins
import copy
import importlib
import json
import os
import shutil
import socket
import subprocess
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


def verifier_branche():
    commande = subprocess.run(
        ["git", "-C", str(ROOT),
         "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    branche = commande.stdout.strip()
    exiger(
        branche == BRANCH,
        "Branche incorrecte : " + repr(branche)
    )


@contextmanager
def protection():
    """Bloque les ecritures courantes et le reseau Python."""
    original_open = builtins.open
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

    protections = [
        patch("builtins.open", open_protege),
        patch("io.open", open_protege),
        patch("os.open", os_open_protege),
        patch("socket.socket.connect", interdit),
        patch("socket.socket.connect_ex", interdit),
        patch("socket.socket.bind", interdit),
        patch("socket.socket.listen", interdit),
        patch("socket.socket.sendto", interdit),
        patch("socket.create_connection", interdit),
        patch("socket.getaddrinfo", interdit),
        patch("os.remove", interdit),
        patch("os.unlink", interdit),
        patch("os.rename", interdit),
        patch("os.replace", interdit),
        patch("os.mkdir", interdit),
        patch("os.makedirs", interdit),
        patch("os.rmdir", interdit),
        patch("os.chmod", interdit),
        patch("os.chown", interdit),
        patch("os.truncate", interdit),
        patch("shutil.rmtree", interdit),
        patch("shutil.move", interdit),
        patch("shutil.copy", interdit),
        patch("shutil.copy2", interdit),
        patch("shutil.copyfile", interdit),
        patch("subprocess.Popen", interdit),
        patch("os.system", interdit),
        patch("os.popen", interdit),
    ]

    from contextlib import ExitStack

    with ExitStack() as pile:
        for element in protections:
            pile.enter_context(element)
        yield


def charger_fixture(chemin):
    exiger(
        chemin.is_file() and not chemin.is_symlink(),
        "Fixture absente ou lien symbolique"
    )

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

    for champ in (
        "source_url",
        "source_nom",
        "date_verification",
    ):
        valeur = preuve.get(champ)
        exiger(
            isinstance(valeur, str) and valeur.strip(),
            "Preuve incomplete : " + champ
        )

    exiger(
        preuve["source_url"].startswith("https://"),
        "Source HTTPS obligatoire"
    )
    exiger(
        preuve.get("verification_humaine") is True,
        "Attestation humaine absente"
    )
    exiger(
        course.get("localisation_france_verifiee") is True,
        "Localisation France non attestee"
    )
    exiger(
        course.get("depart_verifie") is True,
        "Depart non atteste"
    )

    partants = course.get("partants")
    exiger(
        isinstance(partants, list) and partants,
        "Liste des partants absente"
    )

    numeros = []
    actifs = set()

    for cheval in partants:
        exiger(isinstance(cheval, dict),
               "Partant invalide")

        numero = cheval.get("numero")

        exiger(
            type(numero) is int and numero > 0,
            "Numero invalide"
        )
        exiger(
            isinstance(cheval.get("nom"), str)
            and cheval["nom"].strip(),
            "Nom manquant"
        )
        exiger(
            type(cheval.get("non_partant")) is bool,
            "Statut non-partant absent"
        )

        numeros.append(numero)

        if not cheval["non_partant"]:
            actifs.add(numero)

    exiger(
        len(numeros) == len(set(numeros)),
        "Numeros en double"
    )
    exiger(
        len(actifs) >= 5,
        "Moins de cinq partants actifs"
    )

    return course, actifs


def verifier_sortie(sortie, moteur, actifs):
    exiger(isinstance(sortie, dict),
           moteur + " : sortie invalide")
    exiger(sortie.get("moteur") == moteur,
           moteur + " : identite incorrecte")
    exiger(sortie.get("fige") is False,
           moteur + " : FIGE interdit")
    exiger(sortie.get("publication") is False,
           moteur + " : publication interdite")

    statut = sortie.get("statut")

    exiger(
        statut in (
            "ANALYSE_DISPONIBLE",
            "DONNEES_INSUFFISANTES",
            "NON_ANALYSABLE",
        ),
        moteur + " : statut invalide"
    )

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
               "Numero invalide")
        exiger(numero in actifs,
               "Cheval inconnu ou non-partant")

        numeros.append(numero)

    exiger(
        len(numeros) == len(set(numeros)),
        "Doublon de classement"
    )
    exiger(len(classement) <= 5,
           "Plus de cinq positions")
    exiger(len(partiel) <= 5,
           "Classement partiel trop long")

    if statut == "ANALYSE_DISPONIBLE":
        exiger(
            len(classement) == 5,
            "Cinq positions attendues"
        )
    else:
        exiger(
            not classement,
            "Classement complet non justifie"
        )

    return statut, numeros


def charger_moteurs():
    modules = {}

    for nom in MOTEURS:
        module = importlib.import_module(
            "moteurs." + nom.lower()
        )

        exiger(
            getattr(module, "MOTEUR", None) == nom,
            nom + " : identite incorrecte"
        )

        modules[nom] = module

    return modules


def tester_moteurs(modules, course=None, actifs=None):
    resultats = {}

    for nom, module in modules.items():
        module.verifier_noyau()

        exiger(
            module.self_test() is True,
            nom + " : autotest echoue"
        )

        if course is None:
            print(nom, "- autotest OK")
            continue

        entree = copy.deepcopy(course)
        reference = copy.deepcopy(entree)

        sortie = module.analyser_course(entree)

        exiger(
            entree == reference,
            nom + " : entree modifiee"
        )

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
    for variable in (
        "X1000_READ_ONLY",
        "X1000_NO_FIGE",
        "X1000_NO_PUBLICATION",
    ):
        exiger(
            os.getenv(variable) == "1",
            variable + " doit valoir 1"
        )

    verifier_branche()

    ancien_dossier = Path.cwd()

    # Repertoire temporaire cree avant protection.
    with tempfile.TemporaryDirectory() as dossier:
        try:
            os.chdir(dossier)

            # Desactive les .pyc dans ce processus.
            sys.dont_write_bytecode = True

            with protection():
                modules = charger_moteurs()
                tester_moteurs(modules)

                fichiers = (
                    sorted(FIXTURES.glob("*.json"))
                    if FIXTURES.is_dir() else []
                )

                if not fichiers:
                    print(
                        "COURSES REELLES : NON TESTEES"
                    )
                    print(
                        "Aucune fixture attestee disponible"
                    )
                    print(
                        "AUTOTESTS TERMINES - "
                        "VALIDATION REELLE INCOMPLETE"
                    )
                    return 0

                for fichier in fichiers:
                    print("COURSE :", fichier.name)

                    course, actifs = charger_fixture(
                        fichier
                    )

                    resultats = tester_moteurs(
                        modules, course, actifs
                    )

                    exiger(
                        set(resultats) == set(MOTEURS),
                        "Resultats moteurs incomplets"
                    )

                print("DIAGNOSTIC M1-M5 TERMINE")
                print("AUCUN FIGE - AUCUNE PUBLICATION")
                print(
                    "Sources et attestations a "
                    "verifier independamment"
                )

        finally:
            os.chdir(ancien_dossier)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            "ECHEC X1000 :",
            type(erreur).__name__,
            str(erreur),
            file=sys.stderr,
        )
        sys.exit(1)
