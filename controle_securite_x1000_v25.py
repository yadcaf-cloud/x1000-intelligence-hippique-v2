#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — CONTROLE DE SECURITE V2.5

Lecture seule.
Aucun FIGE modifie.
Aucune archive modifiee.
Aucune publication.
Aucune connexion GitHub.
"""

from pathlib import Path
import ast
import hashlib
import sys


RACINE = Path(__file__).resolve().parent

MOTEURS = RACINE / "moteurs_corriges_v24"

FICHIERS_MOTEURS = [
    "m1.py",
    "m2.py",
    "m3.py",
    "m4.py",
    "m5.py",
    "noyau_commun.py",
]

VALIDATEUR = RACINE / "validation_courses_pmu_v25.py"

# Repertoires proteges connus.
# Ajouter ici les autres emplacements reels
# des FIGES et archives du projet.
DOSSIERS_PROTEGES = [
    RACINE / "figes",
    RACINE / "archives",
    RACINE / "data" / "figes",
    RACINE / "data" / "archives",
]


def empreinte(chemin):
    return hashlib.sha256(
        chemin.read_bytes()
    ).hexdigest()


def inventaire_protege():
    inventaire = {}

    for dossier in DOSSIERS_PROTEGES:
        if not dossier.is_dir():
            continue

        for chemin in dossier.rglob("*"):
            if chemin.is_file():
                inventaire[str(chemin)] = empreinte(
                    chemin
                )

    return inventaire


def verifier_syntaxe(chemin):
    texte = chemin.read_text(encoding="utf-8")
    ast.parse(texte, filename=str(chemin))


def main():
    print("X1000 PHOENIX — CONTROLE V2.5")
    print("=" * 45)

    avant = inventaire_protege()

    erreurs = []

    if not MOTEURS.is_dir():
        erreurs.append(
            "Dossier des moteurs corriges absent"
        )
    else:
        for nom in FICHIERS_MOTEURS:
            chemin = MOTEURS / nom

            try:
                verifier_syntaxe(chemin)
                print(f"SYNTAXE OK : {nom}")
            except (OSError, UnicodeError, SyntaxError) as exc:
                erreurs.append(f"{nom} : {exc}")

    if VALIDATEUR.is_file():
        try:
            verifier_syntaxe(VALIDATEUR)
            print("SYNTAXE OK : validateur V2.5")
        except (OSError, UnicodeError, SyntaxError) as exc:
            erreurs.append(
                f"Validateur V2.5 : {exc}"
            )
    else:
        erreurs.append(
            "Validateur V2.5 introuvable"
        )

    apres = inventaire_protege()

    if avant != apres:
        erreurs.append(
            "Modification des fichiers proteges detectee"
        )

    print()
    print("Fichiers proteges controles :", len(avant))
    print("FIGES/archives : comparaison terminee")

    if erreurs:
        print()
        print("VALIDATION INCOMPLETE OU EN ECHEC")
        for erreur in erreurs:
            print("ERREUR :", erreur)
        return 1

    print()
    print("CONTROLES STATIQUES REUSSIS")
    print("Aucune modification detectee")
    print("Compatibilite fonctionnelle V2.5 non prouvee")
    return 0


if __name__ == "__main__":
    sys.exit(main())
