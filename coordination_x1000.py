#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - COORDINATION SECURISEE M1 A M5

MISSION :
- Valider les courses PMU physiquement disputees en France.
- Coordonner cinq analyses independantes deja calculees.
- Accepter les classements detailles du noyau commun.
- Extraire les numeros des chevaux sans modifier les analyses.
- Conserver les classements complets et partiels.
- Refuser les donnees incoherentes ou inventees.
- Produire une empreinte SHA-256 de tracabilite.

SECURITE :
- Aucun moteur execute automatiquement.
- Aucune collecte PMU.
- Aucune prediction inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune modification des archives.
- Aucune ecriture de fichiers.
- Aucune validation officielle automatique.

Validation technique locale uniquement.
"""

from __future__ import annotations

import hashlib
import json
import math

from datetime import datetime, timezone
from typing import Any

from validation_moteurs import (
    MOTEURS,
    ValidationErreur,
    valider_course,
    valider_prediction,
)

from moteurs import noyau_commun


VERSION = "2.4"

STATUTS_VALIDES = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})

STATUT_COMPLET = "VALIDE_NON_PUBLIE"

STATUT_PARTIEL = (
    "COORDINATION_INCOMPLETE_NON_PUBLIE"
)


# ============================================================
# 1. VALIDATION DE L'IDENTIFIANT
# ============================================================

def verifier_identifiant(
    course: dict[str, Any],
) -> str | int:

    identifiant = course.get("id")

    if (
        type(identifiant) not in (str, int)
        or not str(identifiant).strip()
    ):
        raise ValidationErreur(
            "Identifiant de course invalide"
        )

    return identifiant


# ============================================================
# 2. VALIDATION DES CINQ MOTEURS
# ============================================================

def verifier_sorties(
    sorties: Any,
) -> None:

    if not isinstance(sorties, dict):
        raise ValidationErreur(
            "Sorties moteurs invalides"
        )

    if set(sorties) != set(MOTEURS):
        raise ValidationErreur(
            "Resultats exacts de M1 a M5 requis"
        )


# ============================================================
# 3. CONTROLE DES SCORES
# ============================================================

def verifier_note(
    valeur: Any,
    contexte: str,
) -> None:

    if valeur is None:
        return

    if type(valeur) not in (int, float):
        raise ValidationErreur(
            f"{contexte}: note non numerique"
        )

    if not math.isfinite(valeur):
        raise ValidationErreur(
            f"{contexte}: note non finie"
        )

    if not 0 <= valeur <= 100:
        raise ValidationErreur(
            f"{contexte}: note hors limites"
        )


# ============================================================
# 4. EXTRACTION DES CLASSEMENTS DETAILLES
# ============================================================

def extraire_classement(
    moteur: str,
    positions: Any,
    actifs: set[int],
    complet: bool,
    partants: dict[int, str],
) -> tuple[list[int], list[dict[str, Any]]]:
    """
    Convertit un classement detaille en numeros.

    Exemple :
        [
            {
                "position_predite": 1,
                "numero": 9,
                "nom": "Cheval A",
                "score": 82.5,
                "couverture": 1.0,
                "risques": []
            }
        ]

    Devient :
        [9]

    Les details originaux sont conserves.
    """

    if not isinstance(positions, list):
        raise ValidationErreur(
            f"{moteur}: classement invalide"
        )

    limite = 5 if complet else 4

    if complet and len(positions) != 5:
        raise ValidationErreur(
            f"{moteur}: cinq positions exigees"
        )

    if not complet and len(positions) > limite:
        raise ValidationErreur(
            f"{moteur}: classement partiel trop long"
        )

    numeros = []
    details = []

    for index, position in enumerate(
        positions,
        start=1,
    ):

        if not isinstance(position, dict):
            raise ValidationErreur(
                f"{moteur}: position detaillee invalide"
            )

        rang = position.get(
            "position_predite"
        )

        numero = position.get("numero")

        nom = position.get("nom")

        if type(rang) is not int or rang != index:
            raise ValidationErreur(
                f"{moteur}: ordre des positions invalide"
            )

        if type(numero) is not int or numero <= 0:
            raise ValidationErreur(
                f"{moteur}: numero invalide"
            )

        if numero not in actifs:
            raise ValidationErreur(
                f"{moteur}: cheval non-partant ou inconnu"
            )

        if numero in numeros:
            raise ValidationErreur(
                f"{moteur}: numero en double"
            )

        if (
            not isinstance(nom, str)
            or not nom.strip()
            or nom != partants[numero]
        ):
            raise ValidationErreur(
                f"{moteur}: nom du cheval incoherent"
            )

        verifier_note(
            position.get("score"),
            f"{moteur} score",
        )

        couverture = position.get(
            "couverture"
        )

        if couverture is not None:

            if (
                type(couverture) not in (int, float)
                or not math.isfinite(couverture)
                or not 0 <= couverture <= 1
            ):
                raise ValidationErreur(
                    f"{moteur}: couverture invalide"
                )

        risques = position.get("risques", [])

        if not isinstance(risques, list):
            raise ValidationErreur(
                f"{moteur}: risques invalides"
            )

        numeros.append(numero)

        details.append(position.copy())

    if complet:
        valider_prediction(
            moteur,
            numeros,
            actifs,
        )

    return numeros, details


# ============================================================
# 5. ADAPTATION D'UN RESULTAT MOTEUR
# ============================================================

def adapter_sortie_moteur(
    moteur: str,
    sortie: Any,
    course: dict[str, Any],
    actifs: set[int],
    identifiant: str | int,
    partants: dict[int, str],
) -> dict[str, Any]:
    """
    Accepte :
    - Le format historique de cinq numeros.
    - Le format structure V2.4 du noyau commun.

    Les classements partiels restent partiels.
    """

    # --------------------------------------------------------
    # A. FORMAT HISTORIQUE
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
            "details_classement": [],
            "details_partiels": [],
            "format": "LISTE_HISTORIQUE",
            "raison": (
                "Liste historique valide techniquement"
            ),
        }

    # --------------------------------------------------------
    # B. FORMAT STRUCTURE V2.4
    # --------------------------------------------------------

    if not isinstance(sortie, dict):
        raise ValidationErreur(
            f"{moteur}: format invalide"
        )

    if sortie.get("moteur") != moteur:
        raise ValidationErreur(
            f"{moteur}: identite incoherente"
        )

    if (
        type(sortie.get("course_id"))
        is not type(identifiant)
        or sortie.get("course_id") != identifiant
    ):
        raise ValidationErreur(
            f"{moteur}: identifiant incoherent"
        )

    if sortie.get("fige") is not False:
        raise ValidationErreur(
            f"{moteur}: FIGE interdit"
        )

    if sortie.get("publication") is not False:
        raise ValidationErreur(
            f"{moteur}: publication interdite"
        )

    statut = sortie.get("statut")

    if statut not in STATUTS_VALIDES:
        raise ValidationErreur(
            f"{moteur}: statut non autorise"
        )

    # Verification par le noyau commun.
    # Cette fonction doit refuser toute sortie invalide.

    try:
        noyau_commun.verifier_sortie_analyse(
            course,
            sortie,
        )

    except (ValueError, TypeError) as exc:
        raise ValidationErreur(
            f"{moteur}: validation noyau echouee"
        ) from exc

    complet = (
        statut == "ANALYSE_DISPONIBLE"
    )

    classement_brut = sortie.get(
        "classement",
        [],
    )

    partiel_brut = sortie.get(
        "classement_partiel",
        [],
    )

    if not isinstance(classement_brut, list):
        raise ValidationErreur(
            f"{moteur}: classement non liste"
        )

    if not isinstance(partiel_brut, list):
        raise ValidationErreur(
            f"{moteur}: classement partiel non liste"
        )

    if complet:

        if partiel_brut:
            raise ValidationErreur(
                f"{moteur}: partiel non vide "
                "avec analyse complete"
            )

        numeros, details = extraire_classement(
            moteur,
            classement_brut,
            actifs,
            True,
            partants,
        )

        numeros_partiels = []
        details_partiels = []

    else:

        if classement_brut:
            raise ValidationErreur(
                f"{moteur}: classement complet "
                "interdit pour ce statut"
            )

        numeros = []
        details = []

        numeros_partiels, details_partiels = (
            extraire_classement(
                moteur,
                partiel_brut,
                actifs,
                False,
                partants,
            )
        )

        if (
            statut == "NON_ANALYSABLE"
            and numeros_partiels
        ):
            raise ValidationErreur(
                f"{moteur}: partiel interdit "
                "pour course non analysable"
            )

    raison = sortie.get("raison", "")

    if not isinstance(raison, str):
        raison = ""

    return {
        "moteur": moteur,
        "statut": statut,
        "classement": numeros,
        "classement_partiel": numeros_partiels,
        "details_classement": details,
        "details_partiels": details_partiels,
        "format": "RESULTAT_STRUCTURE_V2_4",
        "raison": raison,
    }


# ============================================================
# 6. EMPREINTE DE TRACABILITE
# ============================================================

def calculer_empreinte(
    course: dict[str, Any],
    analyses: dict[str, Any],
) -> str:

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
# 7. COORDINATION CENTRALE
# ============================================================

def coordonner(
    course: dict[str, Any],
    sorties: dict[str, Any],
) -> dict[str, Any]:
    """
    Coordonne les cinq moteurs sans les executer.

    Retourne :
    - VALIDE_NON_PUBLIE si les cinq sont complets.
    - COORDINATION_INCOMPLETE_NON_PUBLIE sinon.
    """

    # Validation initiale de la course.

    actifs = valider_course(course)

    identifiant = verifier_identifiant(
        course
    )

    # Validation complementaire du noyau.

    valide, raison = (
        noyau_commun.verifier_course(course)
    )

    if not valide:
        raise ValidationErreur(
            "Course rejetee par le noyau : "
            + str(raison)
        )

    verifier_sorties(sorties)

    partants = {
        cheval["numero"]: cheval["nom"]
        for cheval in course["partants"]
        if not cheval["non_partant"]
    }

    analyses = {}
    predictions = {}
    incomplets = []

    # Chaque moteur conserve son classement.

    for moteur in MOTEURS:

        analyse = adapter_sortie_moteur(
            moteur=moteur,
            sortie=sorties[moteur],
            course=course,
            actifs=actifs,
            identifiant=identifiant,
            partants=partants,
        )

        analyses[moteur] = analyse

        if (
            analyse["statut"]
            == "ANALYSE_DISPONIBLE"
        ):

            predictions[moteur] = (
                analyse["classement"].copy()
            )

        else:

            incomplets.append(moteur)

    complet = len(incomplets) == 0

    statut_global = (
        STATUT_COMPLET
        if complet
        else STATUT_PARTIEL
    )

    empreinte = calculer_empreinte(
        course,
        analyses,
    )

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
# 8. ALIAS DE COMPATIBILITE
# ============================================================

def coordonner_predictions(
    course: dict[str, Any],
    sorties: dict[str, Any],
) -> dict[str, Any]:

    return coordonner(
        course,
        sorties,
    )


# ============================================================
# 9. EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    print(
        "X1000 V2.4 - Coordination securisee M1-M5"
    )

    print(
        "Mode : validation technique locale"
    )

    print(
        "Cinq moteurs independants requis"
    )

    print(
        "Aucun moteur execute automatiquement"
    )

    print(
        "Aucune publication ni creation de FIGE"
    )
