#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🇸🇳🧠 X1000 — INTELLIGENCE HIPPIQUE V2
RÉPARATION CONTRÔLÉE DES MOTEURS M1 À M5
VERSION 2.4

OBJECTIFS
- Préparer les corrections de classement M1, M2 et M3.
- Contrôler les protections existantes de M4 et M5.
- Renforcer la validation des identifiants du noyau commun.
- Vérifier la syntaxe des six fichiers Python.
- Préserver intégralement les fichiers originaux.
- Ne jamais modifier les FIGÉS ou les archives.
- Ne lancer aucun moteur.
- Ne publier aucun pronostic.
- Ne réaliser aucun commit ni push GitHub.

Les corrections sont préparées dans un dossier distinct.
Les contrôles structurels ne remplacent pas les tests fonctionnels.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile


VERSION = "2.4"

FICHIERS = (
    "m1.py",
    "m2.py",
    "m3.py",
    "m4.py",
    "m5.py",
    "noyau_commun.py",
)


def sha256(chemin: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier."""

    return hashlib.sha256(
        chemin.read_bytes()
    ).hexdigest()


def verifier_syntaxe(texte: str, nom: str) -> ast.Module:
    """Analyse la syntaxe sans exécuter le code."""

    return ast.parse(
        texte,
        filename=nom
    )


def _controle_ordre(arbre: ast.AST) -> bool:
    """Recherche un contrôle d'ordre avec levée d'erreur.

    Vérification structurelle uniquement.
    """

    for noeud in ast.walk(arbre):

        if not isinstance(noeud, ast.If):
            continue

        condition = noeud.test

        if (
            not isinstance(condition, ast.BoolOp)
            or not isinstance(condition.op, ast.And)
        ):
            continue

        noms = {
            element.id
            for element in ast.walk(condition)
            if isinstance(element, ast.Name)
        }

        comparaisons = [
            element
            for element in ast.walk(condition)
            if isinstance(element, ast.Compare)
        ]

        ordre_present = any(
            isinstance(comparaison.left, ast.Name)
            and comparaison.left.id == "score"
            and any(
                isinstance(operateur, ast.Gt)
                for operateur in comparaison.ops
            )
            and any(
                isinstance(element, ast.Name)
                and element.id == "score_precedent"
                for comparateur in comparaison.comparators
                for element in ast.walk(comparateur)
            )
            for comparaison in comparaisons
        )

        erreur_presente = any(
            isinstance(element, ast.Raise)
            for instruction in noeud.body
            for element in ast.walk(instruction)
        )

        if (
            {"score", "score_precedent"}.issubset(noms)
            and ordre_present
            and erreur_presente
        ):
            return True

    return False


def corriger_classement(
    texte: str,
    numero: int
) -> str:
    """Prépare le contrôle décroissant pour M1, M2 et M3."""

    if numero not in (1, 2, 3):
        raise ValueError(
            "Correction limitée aux moteurs M1, M2 et M3"
        )

    nom = f"m{numero}.py"

    arbre = verifier_syntaxe(texte, nom)

    if (
        "score_precedent" in texte
        or _controle_ordre(arbre)
    ):
        raise RuntimeError(
            f"M{numero} : contrôle déjà présent "
            "ou structure différente"
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

    ancre = (
        "            if (\n"
        f'                "score_m{numero}" in cheval\n'
    )

    if texte.count(ancien) != 1:
        raise RuntimeError(
            f"M{numero} : initialisation introuvable "
            "ou non unique"
        )

    if texte.count(ancre) != 1:
        raise RuntimeError(
            f"M{numero} : ancre de validation "
            "introuvable ou non unique"
        )

    lignes = texte.splitlines(keepends=True)

    position = next(
        (
            index
            for index in range(len(lignes) - 1)
            if (
                lignes[index] == "            if (\n"
                and lignes[index + 1]
                == f'                "score_m{numero}" in cheval\n'
            )
        ),
        None
    )

    if position is None:
        raise RuntimeError(
            f"M{numero} : position de validation inconnue"
        )

    precedentes = lignes[
        max(0, position - 30):position
    ]

    calcul_score = any(
        re.match(
            r"^            score\s*=\s*[^=]",
            ligne
        )
        for ligne in precedentes
    )

    if not calcul_score:
        raise RuntimeError(
            f"M{numero} : affectation de score "
            "non confirmée avant le contrôle"
        )

    controle = (
        "            # Contrôle de l'ordre décroissant.\n"
        "            if (\n"
        "                score_precedent is not None\n"
        "                and score > score_precedent\n"
        "            ):\n"
        "                raise RuntimeError(\n"
        f'                    "M{numero} : ordre des scores invalide"\n'
        "                )\n"
        "            score_precedent = score\n\n"
    )

    corrige = texte.replace(
        ancien,
        nouveau,
        1
    )

    corrige = corrige.replace(
        ancre,
        controle + ancre,
        1
    )

    arbre_corrige = verifier_syntaxe(
        corrige,
        nom
    )

    if not _controle_ordre(arbre_corrige):
        raise RuntimeError(
            f"M{numero} : contrôle non retrouvé "
            "après correction"
        )

    return corrige


def verifier_moteur_existant(
    texte: str,
    numero: int
) -> str:
    """Contrôle structurel de la protection M4 ou M5."""

    if numero not in (4, 5):
        raise ValueError(
            "Vérification limitée à M4 et M5"
        )

    arbre = verifier_syntaxe(
        texte,
        f"m{numero}.py"
    )

    if not _controle_ordre(arbre):
        raise RuntimeError(
            f"M{numero} : contrôle d'ordre "
            "non confirmé ; arrêt prudent"
        )

    return texte


def corriger_noyau(texte: str) -> str:
    """Renforce le contrôle des identifiants textuels."""

    verifier_syntaxe(
        texte,
        "noyau_commun.py"
    )

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
            "Noyau commun : structure inconnue, "
            "correction refusée"
        )

    corrige = texte.replace(
        ancien,
        nouveau,
        1
    )

    verifier_syntaxe(
        corrige,
        "noyau_commun.py"
    )

    return corrige


def reparer() -> Path:
    """Prépare les six fichiers dans un dossier isolé."""

    racine = Path(__file__).resolve().parent

    source = racine / "moteurs"

    destination = racine / "moteurs_corriges_v24"

    # ÉTAPE 1 — Vérifier les dossiers.
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError(
            "Dossier moteurs absent "
            "ou lien symbolique interdit"
        )

    if destination.exists() or destination.is_symlink():
        raise RuntimeError(
            "Destination déjà présente : "
            "aucun écrasement autorisé"
        )

    empreintes: dict[str, str] = {}
    corrections: dict[str, str] = {}

    # ÉTAPE 2 — Lire et analyser les six originaux.
    for nom in FICHIERS:

        chemin = source / nom

        if not chemin.is_file() or chemin.is_symlink():
            raise RuntimeError(
                f"Fichier absent ou lien symbolique : {nom}"
            )

        empreintes[nom] = sha256(chemin)

        texte = chemin.read_text(
            encoding="utf-8"
        )

        verifier_syntaxe(
            texte,
            nom
        )

        if nom in ("m1.py", "m2.py", "m3.py"):

            corrige = corriger_classement(
                texte,
                int(nom[1])
            )

        elif nom in ("m4.py", "m5.py"):

            corrige = verifier_moteur_existant(
                texte,
                int(nom[1])
            )

        else:

            corrige = corriger_noyau(
                texte
            )

        verifier_syntaxe(
            corrige,
            nom
        )

        corrections[nom] = corrige

    # ÉTAPE 3 — Préparer une copie temporaire.
    with tempfile.TemporaryDirectory(
        prefix=".x1000_v24_",
        dir=racine
    ) as temporaire:

        preparation = (
            Path(temporaire)
            / "moteurs_corriges_v24"
        )

        preparation.mkdir()

        # ÉTAPE 4 — Écrire seulement les six fichiers.
        for nom, texte in corrections.items():

            chemin = preparation / nom

            chemin.write_text(
                texte,
                encoding="utf-8"
            )

            verifier_syntaxe(
                chemin.read_text(
                    encoding="utf-8"
                ),
                nom
            )

        # ÉTAPE 5 — Contrôler les originaux.
        for nom, empreinte in empreintes.items():

            if sha256(source / nom) != empreinte:
                raise RuntimeError(
                    "Original modifié pendant "
                    f"la préparation : {nom}"
                )

        # ÉTAPE 6 — Refuser tout écrasement.
        if (
            destination.exists()
            or destination.is_symlink()
        ):
            raise RuntimeError(
                "Destination apparue pendant "
                "la préparation"
            )

        # ÉTAPE 7 — Publier uniquement la copie locale.
        os.rename(
            preparation,
            destination
        )

    # ÉTAPE 8 — Rapport local.
    print()
    print("=" * 60)
    print("🇸🇳🧠 X1000 — INTELLIGENCE HIPPIQUE V2")
    print("RÉPARATION CONTRÔLÉE V2.4 PRÉPARÉE")
    print("=" * 60)

    for nom in FICHIERS:
        print(f"SYNTAXE OK : {nom}")

    print()
    print("M1 : correction préparée")
    print("M2 : correction préparée")
    print("M3 : correction préparée")
    print("M4 : contrôle structurel confirmé")
    print("M5 : contrôle structurel confirmé")
    print("NOYAU : validation des identifiants renforcée")

    print()
    print("Originaux : aucune écriture")
    print("FIGÉS : aucune écriture")
    print("Archives : aucune écriture")
    print("Moteurs : aucune exécution")
    print("Publication : aucune")
    print("GitHub : aucun commit ni push")

    print()
    print("Dossier de préparation :")
    print(destination)

    print()
    print(
        "ATTENTION : revue des différences "
        "et tests fonctionnels encore nécessaires."
    )

    return destination


if __name__ == "__main__":

    try:
        reparer()

    except (
        OSError,
        ValueError,
        RuntimeError,
        SyntaxError,
        UnicodeError,
    ) as erreur:

        print(
            f"ERREUR X1000 : {erreur}",
            file=sys.stderr
        )

        sys.exit(1)
