#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX
REPARATION CONTROLEE DES MOTEURS M1 A M5
VERSION 2.4

OBJECTIFS
- Corriger les classements M1, M2 et M3
- Conserver les protections M4 et M5
- Renforcer le noyau commun
- Verifier la syntaxe des six fichiers
- Preserver les fichiers originaux
- Ne jamais modifier les FIGES ou archives
- Ne rien publier sur GitHub
"""

from pathlib import Path
import ast
import hashlib
import shutil
import sys


VERSION = "2.4"

FICHIERS = [
    "m1.py",
    "m2.py",
    "m3.py",
    "m4.py",
    "m5.py",
    "noyau_commun.py",
]


def sha256(chemin):
    return hashlib.sha256(
        chemin.read_bytes()
    ).hexdigest()


def corriger_classement(texte, numero):

    """
    Ajoute le controle de l'ordre des scores
    dans M1, M2 et M3.
    """

    if numero not in (1, 2, 3):
        return texte

    # Eviter une double correction.
    if "score_precedent" in texte:
        raise RuntimeError(
            f"M{numero} : controle deja present "
            "ou structure differente"
        )

    ancien = (
        "        numeros = set()\n\n"
        "        for rang, cheval in enumerate(\n"
    )

    nouveau = (
        "        numeros = set()\n"
        "        score_precedent = None\n\n"
        "        for rang, cheval in enumerate(\n"
    )

    if texte.count(ancien) != 1:
        raise RuntimeError(
            f"M{numero} : emplacement introuvable"
        )

    texte = texte.replace(
        ancien,
        nouveau,
        1
    )

    ancre = (
        '            if (\n'
        f'                "score_m{numero}" in cheval\n'
    )

    controle = (
        "            # Verification du classement\n"
        "            if (\n"
        "                score_precedent is not None\n"
        "                and score > score_precedent\n"
        "            ):\n"
        "                raise RuntimeError(\n"
        f'                    "M{numero} : ordre des scores invalide"\n'
        "                )\n\n"
        "            score_precedent = score\n\n"
    )

    if texte.count(ancre) != 1:
        raise RuntimeError(
            f"M{numero} : validation introuvable"
        )

    return texte.replace(
        ancre,
        controle + ancre,
        1
    )


def verifier_moteur_existant(texte, numero):

    """
    M4 et M5 disposent deja du controle
    d'ordre des scores.
    """

    if "score_precedent" not in texte:
        raise RuntimeError(
            f"M{numero} : controle d'ordre absent"
        )

    return texte


def corriger_noyau(texte):

    """
    Refuse les identifiants non textuels.
    """

    ancien = (
        "        type(identifiant) not in (str, int)\n"
        "        or not str(identifiant).strip()"
    )

    nouveau = (
        "        not isinstance(identifiant, str)\n"
        "        or not identifiant.strip()"
    )

    if texte.count(ancien) != 1:
        raise RuntimeError(
            "Noyau commun : structure inattendue"
        )

    return texte.replace(
        ancien,
        nouveau,
        1
    )


def reparer():

    racine = Path(__file__).resolve().parent

    source = racine / "moteurs"

    destination = racine / "moteurs_corriges_v24"

    if not source.is_dir():
        raise RuntimeError(
            "Dossier moteurs introuvable"
        )

    if destination.exists():
        raise RuntimeError(
            "Le dossier de destination existe deja. "
            "Aucun ecrasement autorise."
        )

    originaux = {}

    corrections = {}

    # ETAPE 1 : lecture des fichiers.
    for nom in FICHIERS:

        chemin = source / nom

        if not chemin.is_file():
            raise RuntimeError(
                f"Fichier manquant : {nom}"
            )

        originaux[nom] = sha256(chemin)

        texte = chemin.read_text(
            encoding="utf-8"
        )

        if nom in ("m1.py", "m2.py", "m3.py"):

            numero = int(nom[1])

            corrige = corriger_classement(
                texte,
                numero
            )

        elif nom in ("m4.py", "m5.py"):

            numero = int(nom[1])

            corrige = verifier_moteur_existant(
                texte,
                numero
            )

        else:

            corrige = corriger_noyau(texte)

        # Controle de syntaxe avant ecriture.
        ast.parse(
            corrige,
            filename=nom
        )

        corrections[nom] = corrige

    # ETAPE 2 : copie separee.
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc"
        )
    )

    # ETAPE 3 : appliquer les corrections
    # uniquement dans la copie.
    for nom, texte in corrections.items():

        chemin = destination / nom

        chemin.write_text(
            texte,
            encoding="utf-8"
        )

    # ETAPE 4 : verifier les originaux.
    for nom, empreinte in originaux.items():

        if sha256(source / nom) != empreinte:
            raise RuntimeError(
                f"ALERTE : original modifie : {nom}"
            )

    # ETAPE 5 : verifier les fichiers corriges.
    for nom in FICHIERS:

        chemin = destination / nom

        ast.parse(
            chemin.read_text(encoding="utf-8"),
            filename=nom
        )

    print()
    print("=" * 55)
    print("X1000 PHOENIX — REPARATION PREPAREE")
    print("=" * 55)

    for nom in FICHIERS:
        print(f"SYNTAXE OK : {nom}")

    print()
    print("M1 : controle de classement ajoute")
    print("M2 : controle de classement ajoute")
    print("M3 : controle de classement ajoute")
    print("M4 : protection conservee")
    print("M5 : protection conservee")
    print("NOYAU : identifiant renforce")
    print()
    print("Fichiers originaux : inchanges")
    print("FIGES : aucune modification")
    print("Archives : aucune modification")
    print("Publication : aucune")
    print("GitHub : aucun commit ni push")
    print()
    print("Dossier corrige :")
    print(destination)
    print()
    print(
        "ATTENTION : tests fonctionnels "
        "V2.4/V2.5 encore necessaires."
    )


if __name__ == "__main__":

    try:
        reparer()

    except (
        OSError,
        ValueError,
        RuntimeError,
        SyntaxError,
    ) as erreur:

        print(
            f"ERREUR X1000 : {erreur}",
            file=sys.stderr
        )

        sys.exit(1)
