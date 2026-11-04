#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — CORRECTIFS CONTROLES V2.4

- Corrige la validation des classements M1, M2 et M3
- Conserve M4 et M5
- Renforce la validation des identifiants de course
- Travaille uniquement sur une copie séparée
- Aucun commit ni push
- Aucune publication
- Aucun accès réseau
- Aucune modification des FIGÉS ou archives d'origine
"""

from pathlib import Path
import argparse
import ast
import hashlib
import shutil


FILES = [
    f"moteurs/m{i}.py"
    for i in range(1, 6)
] + [
    "moteurs/noyau_commun.py"
]


def empreinte(chemin):
    return hashlib.sha256(
        chemin.read_bytes()
    ).hexdigest()


def corriger_moteur(contenu, numero):

    if numero > 3:
        return contenu

    ancien = (
        "        numeros = set()\n\n"
        "        for rang, cheval in enumerate(\n"
    )

    nouveau = (
        "        numeros = set()\n"
        "        score_precedent = None\n\n"
        "        for rang, cheval in enumerate(\n"
    )

    if contenu.count(ancien) != 1:
        raise RuntimeError(
            f"M{numero} : structure inattendue"
        )

    contenu = contenu.replace(
        ancien, nouveau, 1
    )

    ancre = (
        f'            if (\n'
        f'                "score_m{numero}" in cheval\n'
    )

    controle = (
        "            if (\n"
        "                score_precedent is not None\n"
        "                and score > score_precedent\n"
        "            ):\n"
        "                raise RuntimeError(\n"
        '                    "Classement non decroissant en score"\n'
        "                )\n\n"
        "            score_precedent = score\n\n"
    )

    if contenu.count(ancre) != 1:
        raise RuntimeError(
            f"M{numero} : validation inattendue"
        )

    return contenu.replace(
        ancre, controle + ancre, 1
    )


def corriger_noyau(contenu):

    ancien = (
        "        type(identifiant) not in (str, int)\n"
        "        or not str(identifiant).strip()"
    )

    nouveau = (
        "        not isinstance(identifiant, str)\n"
        "        or not identifiant.strip()"
    )

    if contenu.count(ancien) != 1:
        raise RuntimeError(
            "Noyau : structure inattendue"
        )

    return contenu.replace(
        ancien, nouveau, 1
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo",
        required=True,
        help="Dossier source du dépôt"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Nouveau dossier de correction"
    )

    args = parser.parse_args()

    source = Path(args.repo).resolve()
    destination = Path(args.output).resolve()

    if (
        source == destination
        or source in destination.parents
        or destination in source.parents
        or destination.exists()
    ):
        raise ValueError(
            "La destination doit être nouvelle "
            "et séparée de la source"
        )

    avant = {
        fichier: empreinte(source / fichier)
        for fichier in FILES
    }

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.pyc"
        )
    )

    for index, fichier in enumerate(FILES):

        chemin = destination / fichier

        original = chemin.read_text(
            encoding="utf-8"
        )

        if index == 5:
            corrige = corriger_noyau(original)
        else:
            corrige = corriger_moteur(
                original, index + 1
            )

        ast.parse(corrige, filename=fichier)

        chemin.write_text(
            corrige,
            encoding="utf-8"
        )

    for fichier, signature in avant.items():

        if empreinte(source / fichier) != signature:
            raise RuntimeError(
                f"Source modifiée : {fichier}"
            )

    print("X1000 PHOENIX — CORRECTIONS PREPAREES")
    print("Copie :", destination)
    print("Source : inchangée")
    print("FIGÉS et archives source : inchangés")
    print("GitHub : aucune publication")


if __name__ == "__main__":
    main()
