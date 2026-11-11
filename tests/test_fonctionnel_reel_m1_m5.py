#!/usr/bin/env python3
"""
X1000 PHOENIX - Diagnostic controle M1-M5.

Objectifs :
- Controle de la branche autorisee.
- Autotests independants M1 a M5.
- Verification des fixtures de courses reelles.
- Controle des classements et non-partants.
- Protection contre les ecritures courantes.
- Blocage des connexions reseau Python.
- Aucun FIGE, aucune publication.
- Aucune modification des archives.
- Compatibilite Pytest et GitHub Actions.
"""

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

from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

BRANCH = "fix/x1000-v2-reparation-controlee"

DEPOT = "x1000-intelligence-hippique-v2"

MOTEURS = ("M1", "M2", "M3", "M4", "M5")

FIXTURES = ROOT / "tests" / "donnees_reelles"

sys.path.insert(0, str(ROOT))


def exiger(condition, message):
    if not condition:
        raise AssertionError(message)


def verifier_branche():
    """Verifie le depot et la branche de travail."""

    exiger(
        ROOT.name == DEPOT,
        "Depot incorrect : " + ROOT.name
    )

    commande = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "branch",
            "--show-current",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    branche_locale = commande.stdout.strip()

    # GitHub Actions utilise souvent un HEAD detache.
    branche_ci = (
        os.getenv("GITHUB_HEAD_REF")
        or os.getenv("GITHUB_REF_NAME")
        or ""
    )

    if branche_locale:
        branche = branche_locale
    elif os.getenv("GITHUB_ACTIONS") == "true":
        branche = branche_ci
    else:
        branche = ""

    exiger(
        branche == BRANCH,
        "Branche incorrecte : " + repr(branche)
    )

    print("DEPOT :", DEPOT)
    print("BRANCHE :", branche)


@contextmanager
def protection():
    """
    Bloque les ecritures courantes et les connexions
    reseau Python pendant le diagnostic.

    Ce mecanisme n'est pas un bac a sable complet.
    """

    original_open = builtins.open
    original_os_open = os.open

    def open_protege(file, mode="r", *args, **kwargs):
        if any(c in str(mode) for c in "wax+"):
            raise PermissionError(
                "X1000 : ecriture interdite"
            )

        return original_open(
            file, mode, *args, **kwargs
        )

    def os_open_protege(file, flags, *args, **kwargs):
        interdits = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_CREAT
            | os.O_TRUNC
            | os.O_APPEND
        )

        if flags & interdits:
            raise PermissionError(
                "X1000 : ecriture OS interdite"
            )

        return original_os_open(
            file, flags, *args, **kwargs
        )

    def interdit(*args, **kwargs):
        raise PermissionError(
            "X1000 : operation interdite"
        )

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

    with ExitStack() as pile:
        for element in protections:
            pile.enter_context(element)

        yield


def charger_fixture(chemin):
    """Charge et controle une fixture attestee."""

    exiger(
        chemin.is_file()
        and not chemin.is_symlink(),
        "Fixture absente ou lien symbolique"
    )

    with chemin.open(
        "r", encoding="utf-8"
    ) as fichier:
        donnees = json.load(fichier)

    exiger(
        isinstance(donnees, dict),
        "Fixture invalide"
    )

    preuve = donnees.get("preuve")
    course = donnees.get("course")

    exiger(
        isinstance(preuve, dict),
        "Preuve absente"
    )

    exiger(
        isinstance(course, dict),
        "Course absente"
    )

    for champ in (
        "source_url",
        "source_nom",
        "date_verification",
    ):
        valeur = preuve.get(champ)

        exiger(
            isinstance(valeur, str)
            and bool(valeur.strip()),
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
        course.get(
            "localisation_france_verifiee"
        ) is True,
        "Localisation France non attestee"
    )

    exiger(
        course.get("depart_verifie") is True,
        "Depart non atteste"
    )

    partants = course.get("partants")

    exiger(
        isinstance(partants, list)
        and bool(partants),
        "Liste des partants absente"
    )

    numeros = []
    actifs = set()

    for cheval in partants:
        exiger(
            isinstance(cheval, dict),
            "Partant invalide"
        )

        numero = cheval.get("numero")

        exiger(
            type(numero) is int
            and numero > 0,
            "Numero invalide"
        )

        exiger(
            isinstance(cheval.get("nom"), str)
            and bool(cheval["nom"].strip()),
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
    """Controle la sortie sans changer le pronostic."""

    exiger(
        isinstance(sortie, dict),
        moteur + " : sortie invalide"
    )

    exiger(
        sortie.get("moteur") == moteur,
        moteur + " : identite incorrecte"
    )

    exiger(
        sortie.get("fige") is False,
        moteur + " : FIGE interdit"
    )

    exiger(
        sortie.get("publication") is False,
        moteur + " : publication interdite"
    )

    statut = sortie.get("statut")

    statuts_autorises = (
        "ANALYSE_DISPONIBLE",
        "DONNEES_INSUFFISANTES",
        "NON_ANALYSABLE",
    )

    exiger(
        statut in statuts_autorises,
        moteur + " : statut invalide"
    )

    classement = sortie.get("classement", [])
    partiel = sortie.get("classement_partiel", [])

    exiger(
        isinstance(classement, list),
        moteur + " : classement invalide"
    )

    exiger(
        isinstance(partiel, list),
        moteur + " : classement partiel invalide"
    )

    numeros = []

    for cheval in classement + partiel:
        exiger(
            isinstance(cheval, dict),
            moteur + " : position invalide"
        )

        numero = cheval.get("numero")

        exiger(
            type(numero) is int,
            moteur + " : numero invalide"
        )

        exiger(
            numero in actifs,
            moteur + " : cheval inconnu ou non-partant"
        )

        numeros.append(numero)

    exiger(
        len(numeros) == len(set(numeros)),
        moteur + " : doublon de classement"
    )

    exiger(
        len(classement) <= 5,
        moteur + " : plus de cinq positions"
    )

    exiger(
        len(partiel) <= 5,
        moteur + " : classement partiel trop long"
    )

    if statut == "ANALYSE_DISPONIBLE":
        exiger(
            len(classement) == 5,
            moteur + " : cinq positions attendues"
        )

        exiger(
            not partiel,
            moteur + " : classement partiel inattendu"
        )
    else:
        exiger(
            not classement,
            moteur + " : classement complet non justifie"
        )

    return statut, numeros


def charger_moteurs():
    """Charge les cinq moteurs independamment."""

    modules = {}

    for nom in MOTEURS:
        module = importlib.import_module(
            "moteurs." + nom.lower()
        )

        exiger(
            getattr(module, "MOTEUR", None) == nom,
            nom + " : identite incorrecte"
        )

        for fonction in (
            "verifier_noyau",
            "self_test",
            "analyser_course",
        ):
            exiger(
                callable(getattr(module, fonction, None)),
                nom + " : fonction absente : " + fonction
            )

        modules[nom] = module

    return modules


def tester_moteurs(modules, course=None, actifs=None):
    """Execute les controles M1-M5."""

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

        noyau = getattr(
            module, "noyau_commun", None
        )

        exiger(
            noyau is not None
            and callable(
                getattr(
                    noyau,
                    "verifier_sortie_analyse",
                    None,
                )
            ),
            nom + " : validateur commun absent"
        )

        noyau.verifier_sortie_analyse(
            sortie, course
        )

        statut, numeros = verifier_sortie(
            sortie, nom, actifs
        )

        resultats[nom] = {
            "statut": statut,
            "numeros": numeros,
        }

        print(
            nom,
            "-",
            statut,
            numeros,
        )

    return resultats


# CORRECTION PYTEST :
# Cette fonction est un utilitaire interne.
# Pytest ne doit pas la collecter comme un test.
# Evite : fixture 'modules' not found.
tester_moteurs.__test__ = False


def main():
    """Lance le diagnostic controle."""

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
    ancien_bytecode = sys.dont_write_bytecode

    # Le dossier temporaire est cree avant
    # l'activation des protections.
    with tempfile.TemporaryDirectory() as dossier:
        try:
            os.chdir(dossier)

            sys.dont_write_bytecode = True

            with protection():
                modules = charger_moteurs()

                tester_moteurs(modules)

                fichiers = (
                    sorted(FIXTURES.glob("*.json"))
                    if FIXTURES.is_dir()
                    else []
                )

                if not fichiers:
                    print(
                        "COURSES REELLES : NON TESTEES"
                    )

                    print(
                        "Aucune fixture attestee disponible"
                    )

                    print(
                        "AUTOTESTS OK - "
                        "VALIDATION REELLE INCOMPLETE"
                    )

                    return 0

                for fichier in fichiers:
                    print(
                        "COURSE :", fichier.name
                    )

                    course, actifs = charger_fixture(
                        fichier
                    )

                    resultats = tester_moteurs(
                        modules,
                        course,
                        actifs,
                    )

                    exiger(
                        set(resultats) == set(MOTEURS),
                        "Resultats moteurs incomplets"
                    )

                print(
                    "DIAGNOSTIC M1-M5 TERMINE"
                )

                print(
                    "AUCUN FIGE - AUCUNE PUBLICATION"
                )

                print(
                    "Sources et attestations a "
                    "verifier independamment"
                )

        finally:
            os.chdir(ancien_dossier)
            sys.dont_write_bytecode = ancien_bytecode

    return 0


# Empêche egalement la collecte du point d'entree
# comme test par des configurations Pytest larges.
main.__test__ = False


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
