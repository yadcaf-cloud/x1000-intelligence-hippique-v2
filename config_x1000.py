#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 — CONFIGURATION CENTRALE

Intelligence Hippique Humaine.

Principes :
- Courses physiquement disputees en France.
- Donnees reelles obligatoires.
- Aucune simulation.
- Cinq moteurs independants M1 a M5.
- Cinq positions par moteur.
- FIGE uniquement avant depart.
- Revision possible avant depart.
- Historique obligatoire.
- Aucun FIGE retroactif.
- Publication publique interdite.

Ce module ne collecte aucune donnee,
ne lance aucun moteur et ne modifie
aucune archive.
"""

from pathlib import Path
from zoneinfo import ZoneInfo


# ==================================================
# 1. IDENTITE DU PROJET
# ==================================================

NOM_PROJET = "X1000 V2"
DESCRIPTION = "Intelligence Hippique Humaine"
VERSION = "2.0.0"


# ==================================================
# 2. FUSEAU HORAIRE
# ==================================================

FUSEAU_HORAIRE = ZoneInfo("Europe/Paris")


# ==================================================
# 3. REGLES GEOGRAPHIQUES ET SPORTIVES
# ==================================================

PAYS_AUTORISE = "France"

DONNEES_REELLES_OBLIGATOIRES = True

SIMULATION_INTERDITE = True


# ==================================================
# 4. CINQ MOTEURS INDEPENDANTS
# ==================================================

MOTEURS = (
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
)

NOMBRE_POSITIONS = 5


# ==================================================
# 5. POLITIQUE DES FIGES
# ==================================================

FIGE_AVANT_DEPART = True

REVISION_AVANT_DEPART = True

HISTORIQUE_OBLIGATOIRE = True

FIGE_RETROACTIF_INTERDIT = True


# ==================================================
# 6. PUBLICATION
# ==================================================

PUBLICATION_AUTORISEE = False


# ==================================================
# 7. CHEMINS DU PROJET
# ==================================================

RACINE = Path(__file__).resolve().parent

DOSSIER_DONNEES = RACINE / "data"

DOSSIER_ARCHIVES = DOSSIER_DONNEES / "archives"


# ==================================================
# 8. VERIFICATION DE CONFIGURATION
# ==================================================

def verifier_configuration():
    """
    Controle les invariants de securite X1000.

    Les controles restent actifs meme lorsque
    Python est execute en mode optimise (-O).

    Ne modifie aucun fichier.
    """

    controles = {
        "Cinq moteurs obligatoires":
            len(MOTEURS) == 5,

        "Identite des moteurs M1 a M5":
            MOTEURS == (
                "M1",
                "M2",
                "M3",
                "M4",
                "M5",
            ),

        "Moteurs uniques":
            len(set(MOTEURS)) == 5,

        "Cinq positions obligatoires":
            NOMBRE_POSITIONS == 5,

        "Donnees reelles obligatoires":
            DONNEES_REELLES_OBLIGATOIRES is True,

        "Simulation interdite":
            SIMULATION_INTERDITE is True,

        "Pays autorise France":
            PAYS_AUTORISE == "France",

        "FIGE avant depart obligatoire":
            FIGE_AVANT_DEPART is True,

        "Revision avant depart autorisee":
            REVISION_AVANT_DEPART is True,

        "Historique obligatoire":
            HISTORIQUE_OBLIGATOIRE is True,

        "FIGE retroactif interdit":
            FIGE_RETROACTIF_INTERDIT is True,

        "Publication publique interdite":
            PUBLICATION_AUTORISEE is False,

        "Fuseau horaire Paris":
            (
                isinstance(FUSEAU_HORAIRE, ZoneInfo)
                and FUSEAU_HORAIRE.key
                == "Europe/Paris"
            ),

        "Dossier donnees dans le projet":
            DOSSIER_DONNEES == RACINE / "data",

        "Archives dans le dossier donnees":
            DOSSIER_ARCHIVES
            == DOSSIER_DONNEES / "archives",
    }

    erreurs = [
        nom
        for nom, valide in controles.items()
        if not valide
    ]

    if erreurs:
        raise RuntimeError(
            "Configuration X1000 invalide : "
            + "; ".join(erreurs)
        )

    return True


# ==================================================
# 9. EXECUTION DIRECTE
# ==================================================

def main():
    verifier_configuration()

    print("Configuration X1000 V2 validee.")
    print("Projet :", NOM_PROJET)
    print("Version :", VERSION)
    print("Moteurs :", ", ".join(MOTEURS))
    print("Positions par moteur :", NOMBRE_POSITIONS)
    print("Pays autorise :", PAYS_AUTORISE)
    print("Fuseau horaire :", FUSEAU_HORAIRE.key)
    print("Publication publique : desactivee")
    print("FIGE retroactif : interdit")
    print("Historique : obligatoire")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
