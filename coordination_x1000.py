#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2 — Coordination securisee M1-M5.

Mission :
- Valider une course avant depart.
- Controler cinq predictions independantes.
- Conserver les classements de chaque moteur.
- Produire une empreinte SHA-256.
- Ne lancer aucun moteur.
- Ne creer aucun FIGE.
- Ne modifier aucune archive.
- Ne publier aucune prediction.

La validation est technique et locale.
Elle ne constitue pas une validation officielle.
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


def coordonner(
    course: dict[str, Any],
    sorties: dict[str, Any],
) -> dict[str, Any]:
    """
    Valide les sorties deja calculees de M1-M5.

    Aucun moteur n'est execute ici.
    Aucune donnee n'est enregistree.
    """

    # 1. Validation de la course
    actifs = valider_course(course)

    # 2. Validation de l'identifiant
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

    # 3. Verification des cinq moteurs
    if not isinstance(sorties, dict):
        raise ValidationErreur(
            "Sorties moteurs invalides"
        )

    if set(sorties.keys()) != set(MOTEURS):
        raise ValidationErreur(
            "Resultats exacts de M1 a M5 requis"
        )

    # 4. Validation independante des predictions
    predictions = {}

    for moteur in MOTEURS:
        predictions[moteur] = valider_prediction(
            moteur,
            sorties[moteur],
            actifs,
        )

    # 5. Construction de la trace
    try:
        contenu = json.dumps(
            {
                "course": course,
                "predictions": predictions,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Donnees non serialisables "
            "pour la tracabilite"
        ) from exc

    # 6. Empreinte de tracabilite
    empreinte = hashlib.sha256(
        contenu
    ).hexdigest()

    # 7. Resultat technique non publie
    return {
        "statut": "VALIDE_NON_PUBLIE",
        "course_id": identifiant,
        "valide_a": datetime.now(
            timezone.utc
        ).isoformat(),
        "empreinte_sha256": empreinte,
        "predictions_independantes": predictions,
        "publication_autorisee": False,
        "fige_officiel": False,
    }
