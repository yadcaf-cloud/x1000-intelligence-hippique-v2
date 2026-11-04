#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — CORRECTIFS CONTROLES V2.4

OBJECTIFS
---------
- Corriger la validation des classements M1, M2, M3.
- Conserver M4 et M5 sans modification.
- Renforcer la validation des identifiants de course.
- Travailler exclusivement dans une copie separee.
- Verifier la syntaxe avant toute creation du resultat.
- Refuser les structures inattendues.
- Ne jamais modifier les fichiers sources.

INTERDICTIONS
-------------
- Aucune collecte PMU.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune modification des FIGES.
- Aucune modification des archives.
- Aucune publication automatique.
- Aucun commit ni push.
- Aucun acces reseau.

Ce script prepare une copie corrigee.
Il ne remplace pas les tests de regression.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import shutil
import tempfile

from pathlib import Path


FICHIERS = [
    "moteurs/m1.py",
    "moteurs/m2.py",
    "moteurs/m3.py",
    "moteurs/m4.py",
    "moteurs/m5.py",
    "moteurs/noyau_commun.py",
]


def empreinte(chemin: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier."""

    return hashlib.sha256(
        chemin.read_bytes()
    ).hexdigest()


def corriger_moteur(contenu: str, numero: int) -> str:
    """
    Ajoute un controle d'ordre des scores
    aux moteurs M1, M2 et M3.

    M4 et M5 restent strictement inchanges.
    """

    if numero in (4, 5):
        return contenu

    if numero not in (1, 2, 3):
        raise ValueError("Numero de moteur invalide")

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
            f"M{numero} : structure de classement inattendue"
        )

    contenu = contenu.replace(
        ancien,
        nouveau,
        1,
    )

    # Le score doit avoir ete extrait et valide
    # avant de comparer deux positions.

    ancre = (
        '            if (\n'
        f'                "score_m{numero}" in cheval\n'
    )

    controle = (
        "            if (\n"
        "                score_precedent is not None\n"
        "                and score > score_precedent\n"
        "            ):\n"
        "                raise RuntimeError(\n"
        '                    "Ordre des scores invalide"\n'
        "                )\n\n"
        "            score_precedent = score\n\n"
    )

    if contenu.count(ancre) != 1:
        raise RuntimeError(
            f"M{numero} : point d'insertion introuvable"
        )

    # Verifie que l'affectation du score
    # precede le controle ajoute.

    position_ancre = contenu.index(ancre)

    position_score = contenu.rfind(
        '            score = cheval.get("score")',
        0,
        position_ancre,
    )

    if position_score == -1:
        raise RuntimeError(
            f"M{numero} : affectation du score introuvable"
        )

    contenu = contenu.replace(
        ancre,
        controle + ancre,
        1,
    )

    ast.parse(
        contenu,
        filename=f"moteurs/m{numero}.py",
    )

    return contenu


def corriger_noyau(contenu: str) -> str:
    """
    Refuse les identifiants de course
    qui ne sont pas des chaines non vides.
    """

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

    contenu = contenu.replace(
        ancien,
        nouveau,
        1,
    )

    ast.parse(
        contenu,
        filename="moteurs/noyau_commun.py",
    )

    return contenu


def verifier_source(source: Path) -> dict:
    """
    Verifie les six fichiers Python.
    Enregistre leurs empreintes.
    Refuse les liens symboliques.
    """

    if not source.is_dir():
        raise ValueError(
            "Dossier source inexistant"
        )

    signatures = {}

    for fichier in FICHIERS:

        chemin = source / fichier

        if chemin.is_symlink() or not chemin.is_file():
            raise ValueError(
                f"Fichier absent ou lien interdit : {fichier}"
            )

        ast.parse(
            chemin.read_text(encoding="utf-8"),
            filename=fichier,
        )

        signatures[fichier] = empreinte(chemin)

    return signatures


def preparer_correctifs(
    source: Path,
    destination: Path,
) -> None:
    """
    Prepare les corrections en memoire.

    Cree uniquement les six fichiers Python
    dans une copie separee.

    Les archives et les FIGES ne sont pas copies.
    """

    source = source.resolve()
    destination = destination.absolute()

    if (
        source == destination
        or source in destination.parents
        or destination in source.parents
    ):
        raise ValueError(
            "La destination doit etre separee de la source"
        )

    if destination.is_symlink() or destination.exists():
        raise ValueError(
            "La destination doit etre nouvelle"
        )

    signatures = verifier_source(source)

    contenus = {}

    for fichier in FICHIERS:

        original = (
            source / fichier
        ).read_text(encoding="utf-8")

        if fichier == "moteurs/noyau_commun.py":

            corrige = corriger_noyau(original)

        else:

            numero = int(
                Path(fichier).stem[1:]
            )

            corrige = corriger_moteur(
                original,
                numero,
            )

        ast.parse(
            corrige,
            filename=fichier,
        )

        contenus[fichier] = corrige

    # Verification des sources avant ecriture.

    for fichier, signature in signatures.items():

        if empreinte(source / fichier) != signature:
            raise RuntimeError(
                f"Source modifiee : {fichier}"
            )

    # M4 et M5 doivent rester identiques.

    for numero in (4, 5):

        fichier = f"moteurs/m{numero}.py"

        original = (
            source / fichier
        ).read_text(encoding="utf-8")

        if contenus[fichier] != original:
            raise RuntimeError(
                f"M{numero} a ete modifie"
            )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporaire = Path(
        tempfile.mkdtemp(
            prefix=".x1000-correctifs-",
            dir=destination.parent,
        )
    )

    try:

        for fichier, contenu in contenus.items():

            chemin = temporaire / fichier

            chemin.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            chemin.write_text(
                contenu,
                encoding="utf-8",
            )

            ast.parse(
                chemin.read_text(encoding="utf-8"),
                filename=fichier,
            )

        # Nouvelle verification des originaux.

        for fichier, signature in signatures.items():

            if empreinte(source / fichier) != signature:
                raise RuntimeError(
                    f"Source modifiee : {fichier}"
                )

        if destination.exists():
            raise FileExistsError(
                "Destination deja presente"
            )

        temporaire.rename(destination)

    finally:

        if temporaire.exists():
            shutil.rmtree(temporaire)

    print("=" * 55)
    print("X1000 PHOENIX — CORRECTIFS PREPARES")
    print("=" * 55)

    print("M1 : correction preparee")
    print("M2 : correction preparee")
    print("M3 : correction preparee")
    print("M4 : conserve sans modification")
    print("M5 : conserve sans modification")
    print("Noyau commun : correction preparee")

    print("Syntaxe : validee")
    print("Source : inchangee")
    print("FIGES : non copies")
    print("Archives : non copiees")
    print("Collecte PMU : aucune")
    print("Publication : aucune")
    print("GitHub : aucun commit ni push")

    print(f"Copie corrigee : {destination}")
    print("=" * 55)


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "X1000 PHOENIX - Preparation "
            "securisee des correctifs V2.4"
        )
    )

    parser.add_argument(
        "--repo",
        required=True,
        help="Dossier du depot source",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Nouveau dossier de sortie",
    )

    args = parser.parse_args()

    try:

        preparer_correctifs(
            Path(args.repo),
            Path(args.output),
        )

        return 0

    except Exception as erreur:

        print(
            "ECHEC CONTROLE : "
            f"{type(erreur).__name__} : {erreur}"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
