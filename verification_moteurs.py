#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""X1000 V2 - Diagnostic M1 a M5 en lecture seule."""

import ast
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MOTEURS = ("M1", "M2", "M3", "M4", "M5")


def verifier_moteur(nom):
    fichier_normal = RACINE / (nom.lower() + ".py")
    fichier_espace = RACINE / (nom.lower() + ".py ")

    resultat = {
        "moteur": nom,
        "fichier_present": False,
        "nom_fichier_correct": False,
        "syntaxe_valide": False,
        "dependances_presentes": False,
        "analyse_executee": False,
        "etat": "INDISPONIBLE",
        "anomalies": [],
    }

    if fichier_normal.is_file():
        fichier = fichier_normal
        resultat["nom_fichier_correct"] = True
    elif fichier_espace.is_file():
        fichier = fichier_espace
        resultat["anomalies"].append(
            "Espace final dans le nom du fichier"
        )
    else:
        resultat["anomalies"].append(
            "Fichier moteur absent"
        )
        return resultat

    resultat["fichier_present"] = True

    try:
        source = fichier.read_text(encoding="utf-8")
        arbre = ast.parse(source, filename=str(fichier))
        resultat["syntaxe_valide"] = True
    except (OSError, SyntaxError, UnicodeError) as erreur:
        resultat["anomalies"].append(str(erreur))
        return resultat

    fonctions = {
        noeud.name
        for noeud in arbre.body
        if isinstance(
            noeud, (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }

    if "analyser_course" not in fonctions:
        resultat["anomalies"].append(
            "Fonction analyser_course absente"
        )

    if nom == "M1":
        noyau = RACINE / "noyau_commun.py"
        noyau_package = RACINE / "moteurs" / "noyau_commun.py"

        if not noyau.is_file() and not noyau_package.is_file():
            resultat["anomalies"].append(
                "Dependance noyau_commun.py absente"
            )

    resultat["dependances_presentes"] = (
        not any(
            "absente" in anomalie
            for anomalie in resultat["anomalies"]
        )
    )

    if resultat["anomalies"]:
        resultat["etat"] = "CORRECTION_NECESSAIRE"
    else:
        resultat["etat"] = "STRUCTURE_VALIDEE"

    return resultat


def main():
    resultats = [
        verifier_moteur(nom)
        for nom in MOTEURS
    ]

    rapport = {
        "application": "X1000 Intelligence Hippique V2",
        "type": "DIAGNOSTIC_STATIQUE",
        "lecture_seule": True,
        "collecte_pmu": False,
        "publication": False,
        "modification_archives": False,
        "analyses_sportives_executees": False,
        "moteurs": resultats,
    }

    print(json.dumps(
        rapport,
        ensure_ascii=False,
        indent=2,
    ))

    return 0 if all(
        item["etat"] == "STRUCTURE_VALIDEE"
        for item in resultats
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
