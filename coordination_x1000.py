#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - COORDINATION SECURISEE M1-M5

MISSION :
- Valider les courses PMU physiquement disputees en France.
- Controler cinq analyses sportives independantes.
- Accepter les resultats structures des moteurs V2.4.
- Conserver les classements partiels documentes.
- Refuser les classements complets invalides.
- Conserver la compatibilite avec les anciennes listes.
- Produire une empreinte SHA-256 de tracabilite.

SECURITE :
- Aucun moteur execute par le coordinateur.
- Aucune collecte PMU automatique.
- Aucune donnee sportive inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication de predictions.
- Aucune modification des archives.
- Aucune ecriture de fichiers.
- Aucune validation officielle automatique.

La validation est exclusivement technique et locale.
"""

from __future__ import annotations

import hashlib
import json

from datetime import datetime, timezone
from typing import Any

from validation_moteurs import (
    MOTEURS,
    ValidationErreur,
    valider_course,
    valider_prediction,
)


VERSION = "2.4"

STATUTS_ANALYSE = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})

STATUT_COORDINATION_COMPLETE = "VALIDE_NON_PUBLIE"
STATUT_COORDINATION_PARTIELLE = "COORDINATION_INCOMPLETE_NON_PUBLIE"


# ============================================================
# 1. IDENTIFIANT DE COURSE
# ============================================================

def verifier_identifiant(course: dict[str, Any]) -> str | int:
    """
    Verifie la presence d'un identifiant de course.
    """

    identifiant = course.get("id")

    if (
        not isinstance(identifiant, (str, int))
        or isinstance(identifiant, bool)
    ):
        raise ValidationErreur(
            "Identifiant de course absent ou invalide"
        )

    if not str(identifiant).strip():
        raise ValidationErreur(
            "Identifiant de course vide"
        )

    return identifiant


# ============================================================
# 2. VALIDATION DES SORTIES MOTEURS
# ============================================================

def verifier_sorties(
    sorties: dict[str, Any],
) -> None:
    """
    Exige exactement les cinq moteurs M1 a M5.
    """

    if not isinstance(sorties, dict):
        raise ValidationErreur(
            "Sorties moteurs invalides"
        )

    if set(sorties.keys()) != set(MOTEURS):
        raise ValidationErreur(
            "Resultats exacts de M1 a M5 requis"
        )


# ============================================================
# 3. CONTROLE DES CLASSEMENTS PARTIELS
# ============================================================

def valider_classement_partiel(
    moteur: str,
    positions: Any,
    actifs: set[int],
) -> list[int]:
    """
    Valide zero a quatre positions documentees.

    Un classement partiel ne devient jamais
    une prediction complete.
    """

    if not isinstance(positions, list):
        raise ValidationErreur(
            f"{moteur}: classement partiel invalide"
        )

    if len(positions) > 4:
        raise ValidationErreur(
            f"{moteur}: classement partiel trop long"
        )

    if any(
        type(numero) is not int or numero <= 0
        for numero in positions
    ):
        raise ValidationErreur(
            f"{moteur}: numero partiel invalide"
        )

    if len(set(positions)) != len(positions):
        raise ValidationErreur(
            f"{moteur}: doublon dans classement partiel"
        )

    if not set(positions).issubset(actifs):
        raise ValidationErreur(
            f"{moteur}: cheval non-partant ou inconnu"
        )

    return positions.copy()


# ============================================================
# 4. ADAPTATEUR DES RESULTATS MOTEURS
# ============================================================

def adapter_sortie_moteur(
    moteur: str,
    sortie: Any,
    actifs: set[int],
    identifiant: str | int,
) -> dict[str, Any]:
    """
    Accepte deux formats :

    Ancien format :
        [9, 6, 8, 4, 7]

    Nouveau format V2.4 :
        {
            "moteur": "M1",
            "course_id": "...",
            "statut": "ANALYSE_DISPONIBLE",
            "classement": [9, 6, 8, 4, 7],
            "classement_partiel": [],
            "fige": False,
            "publication": False
        }

    Aucun resultat n'est complete artificiellement.
    """

    # --------------------------------------------------------
    # ANCIEN FORMAT : LISTE COMPLETE
    # --------------------------------------------------------

    if isinstance(sortie, list):

        classement = valider_prediction(
            moteur,
            sortie,
            actifs,
        )

        return {
            "moteur": moteur,
            "statut": "ANALYSE_DISPONIBLE",
            "classement": classement,
            "classement_partiel": [],
            "raison": (
                "Ancien format valide techniquement"
            ),
            "format": "LISTE_HISTORIQUE",
        }

    # --------------------------------------------------------
    # NOUVEAU FORMAT : RESULTAT STRUCTURE
    # --------------------------------------------------------

    if not isinstance(sortie, dict):
        raise ValidationErreur(
            f"{moteur}: format de sortie invalide"
        )

    if sortie.get("moteur") != moteur:
        raise ValidationErreur(
            f"{moteur}: identite incoherente"
        )

    course_id = sortie.get("course_id")

    if (
        type(course_id) is not type(identifiant)
        or course_id != identifiant
    ):
        raise ValidationErreur(
            f"{moteur}: identifiant de course incoherent"
        )

    if sortie.get("fige") is not False:
        raise ValidationErreur(
            f"{moteur}: FIGE non autorise"
        )

    if sortie.get("publication") is not False:
        raise ValidationErreur(
            f"{moteur}: publication non autorisee"
        )

    statut = sortie.get("statut")

    if statut not in STATUTS_ANALYSE:
        raise ValidationErreur(
            f"{moteur}: statut non autorise"
        )

    classement_brut = sortie.get("classement")
    partiel_brut = sortie.get("classement_partiel")

    if not isinstance(classement_brut, list):
        raise ValidationErreur(
            f"{moteur}: classement invalide"
        )

    if not isinstance(partiel_brut, list):
        raise ValidationErreur(
            f"{moteur}: classement partiel invalide"
        )

    if statut == "ANALYSE_DISPONIBLE":

        classement = valider_prediction(
            moteur,
            classement_brut,
            actifs,
        )

        if partiel_brut:
            raise ValidationErreur(
                f"{moteur}: classement partiel "
                "non vide avec analyse complete"
            )

        partiel = []

    else:

        if classement_brut:
            raise ValidationErreur(
                f"{moteur}: classement complet "
                "interdit pour ce statut"
            )

        classement = []

        partiel = valider_classement_partiel(
            moteur,
            partiel_brut,
            actifs,
        )

        if statut == "NON_ANALYSABLE" and partiel:
            raise ValidationErreur(
                f"{moteur}: classement partiel "
                "interdit pour course non analysable"
            )

    raison = sortie.get("raison", "")

    if not isinstance(raison, str):
        raison = ""

    return {
        "moteur": moteur,
        "statut": statut,
        "classement": classement,
        "classement_partiel": partiel,
        "raison": raison,
        "format": "RESULTAT_STRUCTURE_V2_4",
    }


# ============================================================
# 5. CONSTRUCTION DE L'EMPREINTE SHA-256
# ============================================================

def calculer_empreinte(
    course: dict[str, Any],
    analyses: dict[str, Any],
) -> str:
    """
    Calcule une empreinte deterministe.

    Aucune donnee n'est enregistree.
    """

    try:

        contenu = json.dumps(
            {
                "version": VERSION,
                "course": course,
                "analyses": analyses,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    except (
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:

        raise ValidationErreur(
            "Donnees non serialisables "
            "pour la tracabilite"
        ) from exc

    return hashlib.sha256(
        contenu
    ).hexdigest()


# ============================================================
# 6. COORDINATION CENTRALE
# ============================================================

def coordonner(
    course: dict[str, Any],
    sorties: dict[str, Any],
) -> dict[str, Any]:
    """
    Coordonne cinq analyses deja calculees.

    Aucun moteur n'est execute.

    Si les cinq moteurs produisent cinq
    positions valides :
        VALIDE_NON_PUBLIE

    Si au moins un moteur est incomplet :
        COORDINATION_INCOMPLETE_NON_PUBLIE

    Les analyses partielles sont conservees.
    """

    # --------------------------------------------------------
    # A. VALIDATION DE LA COURSE
    # --------------------------------------------------------

    actifs = valider_course(course)

    identifiant = verifier_identifiant(
        course
    )

    # --------------------------------------------------------
    # B. VERIFICATION DES CINQ MOTEURS
    # --------------------------------------------------------

    verifier_sorties(sorties)

    # --------------------------------------------------------
    # C. ADAPTATION ET VALIDATION
    # --------------------------------------------------------

    analyses = {}

    predictions = {}

    incomplets = []

    for moteur in MOTEURS:

        resultat = adapter_sortie_moteur(
            moteur=moteur,
            sortie=sorties[moteur],
            actifs=actifs,
            identifiant=identifiant,
        )

        analyses[moteur] = resultat

        if (
            resultat["statut"]
            == "ANALYSE_DISPONIBLE"
        ):

            predictions[moteur] = (
                resultat["classement"].copy()
            )

        else:

            incomplets.append(moteur)

    # --------------------------------------------------------
    # D. STATUT GLOBAL
    # --------------------------------------------------------

    complet = len(incomplets) == 0

    if complet:

        statut_global = (
            STATUT_COORDINATION_COMPLETE
        )

    else:

        statut_global = (
            STATUT_COORDINATION_PARTIELLE
        )

    # --------------------------------------------------------
    # E. EMPREINTE DE TRACABILITE
    # --------------------------------------------------------

    empreinte = calculer_empreinte(
        course,
        analyses,
    )

    # --------------------------------------------------------
    # F. RESULTAT TECHNIQUE NON PUBLIE
    # --------------------------------------------------------

    return {
        "version": VERSION,

        "statut": statut_global,

        "course_id": identifiant,

        "valide_a": datetime.now(
            timezone.utc
        ).isoformat(),

        "empreinte_sha256": empreinte,

        "coordination_complete": complet,

        "nombre_moteurs": len(MOTEURS),

        "moteurs_complets": [
            moteur
            for moteur in MOTEURS
            if moteur not in incomplets
        ],

        "moteurs_incomplets": incomplets,

        "analyses_independantes": analyses,

        "predictions_independantes": (
            predictions if complet else {}
        ),

        "predictions_partielles": {
            moteur: analyses[moteur][
                "classement_partiel"
            ].copy()
            for moteur in incomplets
        },

        "publication_autorisee": False,

        "fige_officiel": False,

        "fige_automatique": False,

        "validation_officielle": False,

        "archives_modifiees": False,
    }


# ============================================================
# 7. COMPATIBILITE AVEC LES ANCIENS APPELS
# ============================================================

def coordonner_predictions(
    course: dict[str, Any],
    sorties: dict[str, Any],
) -> dict[str, Any]:
    """
    Alias compatible avec les appels existants.
    """

    return coordonner(
        course,
        sorties,
    )


# ============================================================
# 8. EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    print(
        "X1000 V2.4 - Coordination securisee M1-M5"
    )

    print(
        "Mode : validation technique locale"
    )

    print(
        "Aucun moteur execute automatiquement"
    )

    print(
        "Aucune publication ni creation de FIGE"
    )
