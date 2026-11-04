#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""X1000 Intelligence Hippique V2 — diagnostic statique M1 à M5.

Lecture seule : aucun import ni exécution des moteurs, aucune écriture.
La validation statique ne démontre pas le fonctionnement sportif.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys


RACINE = Path(__file__).resolve().parent
MOTEURS = tuple(f"M{i}" for i in range(1, 6))
DOSSIERS = (RACINE / "moteurs", RACINE)

INTERFACES_POSSIBLES = (
    "analyser_course",
    "analyser",
    "analyser_partants",
)


def chemins_candidats(nom: str) -> list[Path]:
    """Recherche les emplacements et noms possibles."""

    base = nom.lower() + ".py"

    return [
        dossier / variante
        for dossier in DOSSIERS
        for variante in (base, base + " ")
    ]


def lire_ast(chemin: Path) -> ast.Module:
    """Lit et analyse un fichier Python sans l'exécuter."""

    return ast.parse(
        chemin.read_text(encoding="utf-8-sig"),
        filename=str(chemin),
    )


def chemins_noyau(fichier: Path) -> list[Path]:
    """Localise les noyaux communs possibles."""

    chemins = [
        fichier.parent / "noyau_commun.py",
        RACINE / "moteurs" / "noyau_commun.py",
        RACINE / "noyau_commun.py",
    ]

    return list(dict.fromkeys(chemins))


def verifier_moteur(nom: str) -> dict:
    """Vérifie statiquement un moteur M1 à M5."""

    resultat = {
        "moteur": nom,
        "fichier_present": False,
        "nom_fichier_correct": False,
        "chemin": None,
        "syntaxe_valide": False,
        "interfaces_detectees": [],
        "dependances_presentes": None,
        "analyse_executee": False,
        "etat": "INDISPONIBLE",
        "anomalies": [],
        "avertissements": [],
    }

    if nom not in MOTEURS:
        resultat["anomalies"].append(
            "Nom de moteur inconnu"
        )
        return resultat

    trouves = [
        chemin
        for chemin in chemins_candidats(nom)
        if chemin.is_file() or chemin.is_symlink()
    ]

    if not trouves:
        resultat["anomalies"].append(
            "Fichier moteur absent"
        )
        return resultat

    resultat["fichier_present"] = True

    resultat["chemin"] = [
        str(chemin.relative_to(RACINE))
        for chemin in trouves
    ]

    if len(trouves) != 1:
        resultat["anomalies"].append(
            "Plusieurs fichiers candidats : emplacement ambigu"
        )
        resultat["etat"] = "CORRECTION_NECESSAIRE"
        return resultat

    fichier = trouves[0]

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
        arbre = lire_ast(fichier)

    except (
        OSError,
        UnicodeError,
        SyntaxError,
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
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    resultat["interfaces_detectees"] = sorted(
        fonctions.intersection(INTERFACES_POSSIBLES)
    )

    if not resultat["interfaces_detectees"]:
        resultat["avertissements"].append(
            "Aucune interface conventionnelle détectée ; "
            "contrat réel à vérifier"
        )

    # Détecter les imports statiques du noyau commun.
    references_noyau = any(
        (
            isinstance(noeud, ast.Import)
            and any(
                alias.name == "noyau_commun"
                or alias.name.endswith(".noyau_commun")
                for alias in noeud.names
            )
        )
        or (
            isinstance(noeud, ast.ImportFrom)
            and (
                (
                    noeud.module is not None
                    and (
                        noeud.module == "noyau_commun"
                        or noeud.module.endswith(
                            ".noyau_commun"
                        )
                    )
                )
                or (
                    noeud.module in (None, "moteurs")
                    and any(
                        alias.name == "noyau_commun"
                        for alias in noeud.names
                    )
                )
            )
        )
        for noeud in ast.walk(arbre)
    )

    if references_noyau:
        existants = [
            chemin
            for chemin in chemins_noyau(fichier)
            if chemin.is_file() or chemin.is_symlink()
        ]

        if not existants:
            resultat["dependances_presentes"] = False
            resultat["anomalies"].append(
                "noyau_commun.py référencé mais absent"
            )

        else:
            if len(existants) > 1:
                resultat["avertissements"].append(
                    "Plusieurs noyaux communs présents : "
                    "résolution d'import non garantie"
                )

            erreurs = []

            for noyau in existants:
                if noyau.is_symlink():
                    erreurs.append(
                        "Lien symbolique interdit : "
                        f"{noyau.relative_to(RACINE)}"
                    )
                    continue

                try:
                    lire_ast(noyau)

                except (
                    OSError,
                    UnicodeError,
                    SyntaxError,
                    ValueError,
                ) as erreur:
                    erreurs.append(
                        "Noyau invalide "
                        f"({noyau.relative_to(RACINE)}) : "
                        f"{erreur}"
                    )

            resultat["dependances_presentes"] = (
                not erreurs
            )

            resultat["anomalies"].extend(erreurs)

    else:
        resultat["avertissements"].append(
            "Dépendances non certifiées : "
            "imports dynamiques et externes non évalués"
        )

    resultat["etat"] = (
        "CORRECTION_NECESSAIRE"
        if resultat["anomalies"]
        else "STRUCTURE_VALIDEE"
    )

    return resultat


def main() -> int:
    """Produit le rapport JSON des cinq moteurs."""

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
        "modification_figes": False,
        "analyses_sportives_executees": False,
        "note": (
            "STRUCTURE_VALIDEE signifie uniquement "
            "qu'aucune anomalie bloquante vérifiée "
            "n'a été trouvée. Les imports, l'interface "
            "effective et les performances ne sont "
            "pas validés."
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
            resultat["etat"] == "STRUCTURE_VALIDEE"
            for resultat in resultats
        )
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
