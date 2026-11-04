#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — REPARATION CONTROLEE V2.4

Correction :
- Fonction verifier_sortie_analyse manquante.
- Conservation des moteurs M1, M2, M3, M4, M5.
- Sauvegarde du noyau original.
- Verification syntaxique.
- Verification du chargement des cinq moteurs.
- Aucun commit ni push.
- Aucune publication.
- Aucun FIGE.
- Aucune modification des archives.
"""

from pathlib import Path
import ast
import importlib
import os
import sys
import tempfile


RACINE = Path(__file__).resolve().parent

NOYAU = RACINE / "moteurs" / "noyau_commun.py"

SAUVEGARDE = RACINE / "moteurs" / (
    "noyau_commun.py.sauvegarde"
)

MARQUEUR = "# 8. SECURITE JSON"


CORRECTION = '''
# ============================================================
# 7 BIS. VALIDATION SECURISEE DES SORTIES M1 A M5
# ============================================================

def verifier_sortie_analyse(resultat):
    """
    Valide une sortie d'analyse sportive.

    Aucun FIGE, aucune publication,
    aucune modification des archives.
    """

    if not isinstance(resultat, dict):
        raise ValueError(
            "Sortie d'analyse invalide"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_VALIDES:
        raise ValueError(
            "Statut d'analyse invalide"
        )

    if resultat.get("fige") is not False:
        raise ValueError(
            "FIGE interdit"
        )

    if resultat.get("publication") is not False:
        raise ValueError(
            "Publication interdite"
        )

    moteur = resultat.get("moteur")

    if moteur not in (
        "M1", "M2", "M3", "M4", "M5"
    ):
        raise ValueError(
            "Identite du moteur invalide"
        )

    if str(resultat.get("version")) != VERSION:
        raise ValueError(
            "Version incompatible"
        )

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(classement, list):
        raise ValueError(
            "Classement invalide"
        )

    if not isinstance(partiel, list):
        raise ValueError(
            "Classement partiel invalide"
        )

    if statut == STATUT_DISPONIBLE:

        if len(classement) != 5 or partiel:
            raise ValueError(
                "Cinq positions obligatoires"
            )

        positions = classement

    elif statut == STATUT_INSUFFISANT:

        if classement or len(partiel) >= 5:
            raise ValueError(
                "Classement partiel incoherent"
            )

        positions = partiel

    else:

        if classement or partiel:
            raise ValueError(
                "Classement interdit"
            )

        positions = []

    numeros = set()

    for indice, cheval in enumerate(
        positions, start=1
    ):

        if not isinstance(cheval, dict):
            raise ValueError(
                "Position invalide"
            )

        numero = cheval.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
        ):
            raise ValueError(
                "Numero invalide"
            )

        if numero in numeros:
            raise ValueError(
                "Numero en double"
            )

        numeros.add(numero)

        if (
            type(cheval.get("position_predite"))
            is not int
            or cheval["position_predite"] != indice
        ):
            raise ValueError(
                "Position incoherente"
            )

        if note_valide(
            cheval.get("score")
        ) is None:
            raise ValueError(
                "Score invalide"
            )

        couverture = nombre_fini(
            cheval.get("couverture")
        )

        if (
            couverture is None
            or not 0 <= couverture <= 1
        ):
            raise ValueError(
                "Couverture invalide"
            )

    return True


'''


def verifier_syntaxe(texte, nom):
    ast.parse(texte, filename=str(nom))


def reparer():

    print("=" * 55)
    print("X1000 PHOENIX — REPARATION CONTROLEE")
    print("=" * 55)

    if not NOYAU.is_file():
        raise FileNotFoundError(
            f"Noyau introuvable : {NOYAU}"
        )

    original = NOYAU.read_bytes()
    texte = original.decode("utf-8-sig")

    verifier_syntaxe(texte, NOYAU)

    arbre = ast.parse(texte)

    fonctions = {
        noeud.name
        for noeud in arbre.body
        if isinstance(
            noeud,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }

    if "verifier_sortie_analyse" in fonctions:
        print("Fonction deja presente.")
        print("Aucune modification necessaire.")
        return

    if MARQUEUR not in texte:
        raise RuntimeError(
            "Emplacement de correction introuvable"
        )

    if texte.count(MARQUEUR) != 1:
        raise RuntimeError(
            "Emplacement de correction ambigu"
        )

    nouveau = texte.replace(
        MARQUEUR,
        CORRECTION + MARQUEUR,
        1
    )

    verifier_syntaxe(nouveau, NOYAU)

    # Ne jamais ecraser une sauvegarde existante.
    if not SAUVEGARDE.exists():
        with SAUVEGARDE.open("xb") as fichier:
            fichier.write(original)

        print("Sauvegarde originale creee.")
    else:
        if SAUVEGARDE.read_bytes() != original:
            raise RuntimeError(
                "Sauvegarde existante differente. "
                "Correction annulee pour securite."
            )

    # Ecriture atomique dans le meme dossier.
    temporaire = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=NOYAU.parent,
            prefix=".x1000_reparation_",
            suffix=".tmp",
            delete=False,
        ) as fichier:
            temporaire = Path(fichier.name)
            fichier.write(nouveau.encode("utf-8"))

        os.replace(temporaire, NOYAU)

    finally:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)

    print("Correction inseree.")
    print("Syntaxe Python : OK")


def verifier_moteurs():

    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))

    importlib.invalidate_caches()

    noyau = importlib.import_module(
        "moteurs.noyau_commun"
    )

    fonction = getattr(
        noyau,
        "verifier_sortie_analyse",
        None
    )

    if not callable(fonction):
        raise RuntimeError(
            "Fonction toujours absente"
        )

    if str(noyau.VERSION) != "2.4":
        raise RuntimeError(
            "Version du noyau incorrecte"
        )

    print("Noyau commun V2.4 : OK")

    for numero in range(1, 6):

        nom = f"M{numero}"

        module = importlib.import_module(
            f"moteurs.m{numero}"
        )

        if getattr(module, "MOTEUR", None) != nom:
            raise RuntimeError(
                f"Identite incorrecte : {nom}"
            )

        if str(getattr(module, "VERSION", "")) != "2.4":
            raise RuntimeError(
                f"Version incorrecte : {nom}"
            )

        if not callable(
            getattr(module, "analyser_course", None)
        ):
            raise RuntimeError(
                f"Analyse indisponible : {nom}"
            )

        print(f"{nom} : IMPORT OK")

    print("Chargement M1-M5 : OK")


def main():

    try:
        reparer()
        verifier_moteurs()

        print("=" * 55)
        print("REPARATION ET IMPORTS : OK")
        print("AUCUNE PUBLICATION")
        print("AUCUN FIGE")
        print("AUCUN COMMIT")
        print("AUCUN PUSH")
        print("=" * 55)

        return 0

    except Exception as erreur:

        print(
            f"ECHEC : {type(erreur).__name__}: "
            f"{erreur}",
            file=sys.stderr
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
