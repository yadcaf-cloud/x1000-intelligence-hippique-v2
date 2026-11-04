#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — REPARATION CONTROLEE V2.4 / V2.5

- Une seule commande de réparation locale
- Sauvegarde avant modification
- Validation JSON stricte
- Tests de régression V2.5
- Contrôles syntaxiques V2.4 / V2.5 / M1-M5
- Autotests des cinq moteurs
- Aucun accès réseau
- Aucun commit, push ou publication
- Aucun changement des FIGÉS ou archives

Utilisation :
    python reparation_x1000.py
    python reparation_x1000.py --apply
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys

from datetime import datetime, timezone
from pathlib import Path


BRANCHE = "fix/x1000-v2-reparation-controlee"

VALIDATEUR = Path("validation_courses_pmu_v25.py")

FICHIERS = [
    Path("audit_collecte_pmu.py"),
    VALIDATEUR,
    Path("moteurs/noyau_commun.py"),
    *[
        Path(f"moteurs/m{i}.py")
        for i in range(1, 6)
    ],
]

ANCIEN_CHARGEMENT = '''document = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )'''

NOUVEAU_CHARGEMENT = '''document = charger_json_strict(
            path.read_text(
                encoding="utf-8-sig"
            )
        )'''

FONCTIONS_JSON = '''
def refuser_doublons(paires):
    resultat = {}

    for cle, valeur in paires:
        if cle in resultat:
            raise ValueError(
                f"Clé JSON dupliquée : {cle}"
            )
        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur):
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def charger_json_strict(texte):
    return json.loads(
        texte,
        object_pairs_hook=refuser_doublons,
        parse_constant=refuser_constante,
    )


'''

def git(*arguments):
    resultat = subprocess.run(
        ["git", *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return resultat.stdout.strip()


def verifier_depot():
    if not Path(".git").exists():
        raise RuntimeError(
            "Exécuter depuis la racine du dépôt Git."
        )

    branche = git("branch", "--show-current")

    if branche != BRANCHE:
        raise RuntimeError(
            f"Branche interdite : {branche}"
        )

    if git("status", "--porcelain"):
        raise RuntimeError(
            "Dépôt local non propre. "
            "Conserver les changements existants "
            "avant la réparation."
        )

    for fichier in FICHIERS:
        if not fichier.is_file():
            raise RuntimeError(
                f"Fichier manquant : {fichier}"
            )

    print("Branche autorisée :", branche)
    print("Fichiers requis présents : OK")


def verifier_syntaxe(nom, contenu):
    ast.parse(contenu, filename=str(nom))


def construire_correctif(source):
    if ANCIEN_CHARGEMENT not in source:
        raise RuntimeError(
            "Chargement JSON inattendu. "
            "Correction automatique refusée."
        )

    if "def charger_json_strict(" in source:
        raise RuntimeError(
            "Un chargeur strict existe déjà. "
            "Inspection manuelle nécessaire."
        )

    repere = "def iso_date(value):"

    if repere not in source:
        raise RuntimeError(
            "Point d'insertion introuvable."
        )

    corrige = source.replace(
        repere,
        FONCTIONS_JSON + repere,
        1,
    )

    corrige = corrige.replace(
        ANCIEN_CHARGEMENT,
        NOUVEAU_CHARGEMENT,
        1,
    )

    verifier_syntaxe(VALIDATEUR, corrige)

    return corrige


def tester_json_strict():
    exemples_invalides = [
        '{"id":1,"id":2}',
        '{"score":NaN}',
        '{"score":Infinity}',
        '{"score":-Infinity}',
        '{"courses": [}',
    ]

    espace = {}

    exec(
        compile(
            "import json\n" + FONCTIONS_JSON,
            "<test-json>",
            "exec",
        ),
        espace,
    )

    charger = espace["charger_json_strict"]

    for exemple in exemples_invalides:
        try:
            charger(exemple)
        except ValueError:
            continue

        raise AssertionError(
            f"JSON invalide accepté : {exemple}"
        )

    resultat = charger(
        '{"courses":[{"id":"TEST"}]}'
    )

    assert resultat["courses"][0]["id"] == "TEST"

    print("Tests JSON strict : OK")


def executer_tests():
    commandes = [
        [
            sys.executable,
            "validation_courses_pmu_v25.py",
            "--self-test",
        ],
        *[
            [
                sys.executable,
                "-m",
                f"moteurs.m{i}",
                "--self-test",
            ]
            for i in range(1, 6)
        ],
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "test_coordination_x1000",
        ],
    ]

    echecs = []

    for commande in commandes:
        print("\nTEST :", " ".join(commande))

        resultat = subprocess.run(
            commande,
            capture_output=True,
            text=True,
            timeout=120,
            env=__import__("os").environ | {
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        if resultat.stdout:
            print(resultat.stdout[-4000:])

        if resultat.returncode != 0:
            echecs.append(
                (" ".join(commande), resultat.stderr[-2000:])
            )

    if echecs:
        for commande, erreur in echecs:
            print("ÉCHEC :", commande)
            print(erreur)

        raise RuntimeError(
            f"{len(echecs)} série(s) de tests en échec."
        )

    print("\nTous les autotests exécutés : OK")


def sauvegarder():
    dossier = Path("_sauvegarde_x1000") / (
        datetime.now(timezone.utc)
        .strftime("%Y%m%d_%H%M%S_%f")
    )

    dossier.mkdir(parents=True, exist_ok=False)

    destination = dossier / VALIDATEUR
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(VALIDATEUR, destination)

    print("Sauvegarde :", destination)

    return destination


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer la correction localement.",
    )

    args = parser.parse_args()

    verifier_depot()

    for fichier in FICHIERS:
        contenu = fichier.read_text(
            encoding="utf-8-sig"
        )
        verifier_syntaxe(fichier, contenu)

    print("Syntaxe des fichiers : OK")

    tester_json_strict()

    original = VALIDATEUR.read_text(
        encoding="utf-8"
    )

    corrige = construire_correctif(original)

    if not args.apply:
        print("\nMODE SIMULATION")
        print("Correction préparée et syntaxe vérifiée.")
        print("Aucun fichier modifié.")
        print("Pour appliquer :")
        print(
            "python reparation_x1000.py --apply"
        )
        return 0

    sauvegarde = sauvegarder()

    try:
        VALIDATEUR.write_text(
            corrige,
            encoding="utf-8",
        )

        executer_tests()

    except Exception:
        shutil.copy2(
            sauvegarde,
            VALIDATEUR,
        )

        print(
            "Échec : validateur restauré "
            "depuis la sauvegarde."
        )
        raise

    print("\nREPARATION LOCALE TERMINEE")
    print("Validation JSON renforcée : OUI")
    print("Tests exécutés : OUI")
    print("Moteurs modifiés : NON")
    print("FIGÉS modifiés : NON")
    print("Archives modifiées : NON")
    print("Commit : NON")
    print("Push : NON")
    print("Publication : NON")
    print(
        "Attention : vérification officielle "
        "des courses toujours NON."
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print(
            f"REPARATION INTERROMPUE : {erreur}",
            file=sys.stderr,
        )
        sys.exit(1)
