"""Coordination et validation de sorties M1-M5, sans publication."""
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
    sorties: dict[str, Any]
) -> dict[str, Any]:
    """Valide cinq sorties déjà calculées; ne lance aucun moteur."""

    actifs = valider_course(course)

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

    if not isinstance(sorties, dict):
        raise ValidationErreur(
            "Sorties moteurs invalides"
        )

    if set(sorties) != set(MOTEURS):
        raise ValidationErreur(
            "Résultats exacts de M1 à M5 requis"
        )

    predictions = {
        moteur: valider_prediction(
            moteur,
            sorties[moteur],
            actifs
        )
        for moteur in MOTEURS
    }

    try:
        contenu = json.dumps(
            {
                "course": course,
                "predictions": predictions
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Données non sérialisables pour la traçabilité"
        ) from exc

    return {
        "statut": "VALIDE_NON_PUBLIE",
        "course_id": identifiant,
        "valide_a": datetime.now(timezone.utc).isoformat(),
        "empreinte_sha256": hashlib.sha256(
            contenu
        ).hexdigest(),
        "predictions_independantes": predictions,
        "publication_autorisee": False,
        "fige_officiel": False,
    }
