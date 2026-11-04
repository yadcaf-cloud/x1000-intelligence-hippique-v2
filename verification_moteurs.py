#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""X1000 Intelligence Hippique V2 — diagnostic statique M1 à M5.

Aucun module moteur n'est importé ou exécuté.
Aucun fichier n'est modifié.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


RACINE = Path(__file__).resolve().parent

MOTEURS = tuple(
    f"M{i}" for i in range(1, 6)
)

DOSSIERS = (
    RACINE / "moteurs",
    RACINE,
)


def candidats(nom: str) -> list[Path]:
    """Recherche les emplacements et noms possibles."""

    base = nom.lower() + ".py"

    return [
        dossier / variante
        for dossier in DOSSIERS
        for variante in (
            base,
            base + " ",
        )
    ]


def verifier_moteur(nom: str) -> dict:
    """Vérifie statiquement un moteur sans l'exécuter."""

    resultat = {
        "moteur": nom,
        "fichier_present": False,
        "nom_fichier_correct": False,
        "chemin": None,
        "syntaxe_valide": False,
        "fonction_analyser_course_presente": False,
        "dependances_presentes": None,
        "analyse_executee": False,
        "etat": "INDISPONIBLE",
        "anomalies": [],
    }

    existants = [
        chemin
        for chemin in candidats(nom)
        if chemin.is_file() or chemin.is_symlink()
    ]

    if not existants:
        resultat["anomalies"].append(
            "Fichier moteur absent "
            "(racine et dossier moteurs/)"
        )
        return resultat

    if len(existants) != 1:
        resultat["anomalies"].append(
            "Plusieurs fichiers candidats : choix ambigu"
        )

        resultat["chemin"] = [
            str(chemin.relative_to(RACINE))
            for chemin in existants
        ]

        resultat["etat"] = "CORRECTION_NECESSAIRE"
        return resultat

    fichier = existants[0]

    resultat["fichier_present"] = True

    resultat["chemin"] = str(
        fichier.relative_to(RACINE)
    )

    resultat["nom_fichier_correct"] = (
        fichier.name == nom.lower() + ".py"
    )

    if not resultat["nom_fichier_correct"]:
        resultat["anomalies"].append(
            "Espace final dans le nom du fichier"
        )

    if fichier.is_symlink():
        resultat["anomalies"].append(
            "Lien symbolique non accepté"
        )

        resultat["etat"] = "CORRECTION_NECESSAIRE"
        return resultat

    try:
        source = fichier.read_text(
            encoding="utf-8-sig"
        )

        arbre = ast.parse(
            source,
            filename=str(fichier)
        )

    except (
        OSError,
        SyntaxError,
        UnicodeError,
        ValueError,
    ) as erreur:

        resultat["anomalies"].append(
            "Lecture ou syntaxe invalide : "
            f"{type(erreur).__name__}: {erreur}"
        )

        resultat["etat"] = "CORRECTION_NECESSAIRE"
        return resultat

    resultat["syntaxe_valide"] = True

    fonctions = {
        noeud.name
        for noeud in arbre.body
        if isinstance(
            noeud,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            )
        )
    }

    resultat["fonction_analyser_course_presente"] = (
        "analyser_course" in fonctions
    )

    if not resultat[
        "fonction_analyser_course_presente"
    ]:
        resultat["anomalies"].append(
            "Fonction de premier niveau "
            "analyser_course absente"
        )

    # Vérification ciblée du noyau commun de M1.
    # Les autres dépendances ne sont pas vérifiées.

    if nom == "M1":

        chemins_noyau = (
            fichier.parent / "noyau_commun.py",
            RACINE / "moteurs" / "noyau_commun.py",
        )

        noyaux = list(
            dict.fromkeys(chemins_noyau)
        )

        valides = [
            chemin
            for chemin in noyaux
            if (
                chemin.is_file()
                and not chemin.is_symlink()
            )
        ]

        if not valides:
            resultat["anomalies"].append(
                "Dépendance noyau_commun.py absente"
            )

            resultat["dependances_presentes"] = False

        else:
            noyau_correct = True

            for noyau in valides:

                try:
                    ast.parse(
                        noyau.read_text(
                            encoding="utf-8-sig"
                        ),
                        filename=str(noyau)
                    )

                except (
                    OSError,
                    SyntaxError,
                    UnicodeError,
                    ValueError,
                ) as erreur:

                    noyau_correct = False

                    resultat["anomalies"].append(
                        "Noyau commun invalide : "
                        f"{erreur}"
                    )

            resultat["dependances_presentes"] = (
                noyau_correct
            )

    # Pour M2 à M5, None signifie :
    # dépendances non évaluées.

    resultat["etat"] = (
        "STRUCTURE_VALIDEE"
        if not resultat["anomalies"]
        else "CORRECTION_NECESSAIRE"
    )

    return resultat


def main() -> int:
    """Exécute le diagnostic statique des cinq moteurs."""

    resultats = [
        verifier_moteur(nom)
        for nom in MOTEURS
    ]

    rapport = {
        "application": (
            "X1000 Intelligence Hippique V2"
        ),
        "type": "DIAGNOSTIC_STATIQUE",
        "lecture_seule": True,
        "collecte_pmu": False,
        "publication": False,
        "modification_archives": False,
        "analyses_sportives_executees": False,
        "note": (
            "STRUCTURE_VALIDEE ne garantit pas "
            "que le moteur soit opérationnel. "
            "Les dépendances externes, imports "
            "dynamiques et résultats sportifs "
            "ne sont pas vérifiés."
        ),
        "moteurs": resultats,
    }

    print(
        json.dumps(
            rapport,
            ensure_ascii=False,
            indent=2,
        )
    )

    return (
        0
        if all(
            item["etat"] == "STRUCTURE_VALIDEE"
            for item in resultats
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
