"""Configuration centrale de X1000 V2."""

from pathlib import Path
from zoneinfo import ZoneInfo

NOM_PROJET = "X1000 V2"
DESCRIPTION = "Intelligence Hippique Humaine"
VERSION = "2.0.0"

FUSEAU_HORAIRE = ZoneInfo("Europe/Paris")

# Courses physiquement disputees en France.
PAYS_AUTORISE = "France"
DONNEES_REELLES_OBLIGATOIRES = True
SIMULATION_INTERDITE = True

# Cinq moteurs independants.
MOTEURS = ("M1", "M2", "M3", "M4", "M5")
NOMBRE_POSITIONS = 5

# Politique des pronostics FIGE.
FIGE_AVANT_DEPART = True
REVISION_AVANT_DEPART = True
HISTORIQUE_OBLIGATOIRE = True
FIGE_RETROACTIF_INTERDIT = True

# Publication desactivee pendant l'installation.
PUBLICATION_AUTORISEE = False

RACINE = Path(__file__).resolve().parent
DOSSIER_DONNEES = RACINE / "data"
DOSSIER_ARCHIVES = DOSSIER_DONNEES / "archives"


def verifier_configuration():
    assert len(MOTEURS) == 5
    assert len(set(MOTEURS)) == 5
    assert NOMBRE_POSITIONS == 5
    assert DONNEES_REELLES_OBLIGATOIRES
    assert SIMULATION_INTERDITE
    assert FIGE_RETROACTIF_INTERDIT
    assert not PUBLICATION_AUTORISEE
    return True


if __name__ == "__main__":
    verifier_configuration()
    print("Configuration X1000 V2 validee.")
    print("Moteurs :", ", ".join(MOTEURS))
    print("Publication publique : desactivee")
