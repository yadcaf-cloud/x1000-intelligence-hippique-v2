"""Validation défensive des courses et des sorties M1-M5.

Ce module ne collecte aucune donnée, ne lance aucun moteur
et ne publie rien.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MOTEURS = tuple(f"M{i}" for i in range(1, 6))
MAX_AVANCE_DEPART = timedelta(days=30)


class ValidationErreur(ValueError):
    """Donnée de course ou prédiction non conforme."""


def _numero(valeur: Any, contexte: str) -> int:
    if type(valeur) is not int or valeur <= 0:
        raise ValidationErreur(
            f"{contexte}: numéro entier positif exigé"
        )
    return valeur


def valider_course(course: dict[str, Any]) -> set[int]:
    """Retourne les numéros actifs d'une course validée.

    Les indicateurs de vérification doivent provenir
    d'un collecteur fiable.
    """
    if not isinstance(course, dict):
        raise ValidationErreur("Course invalide")

    if course.get("localisation_france_verifiee") is not True:
        raise ValidationErreur(
            "Localisation France non vérifiée"
        )

    if course.get("depart_verifie") is not True:
        raise ValidationErreur("Départ non vérifié")

    depart = course.get("depart")

    if not isinstance(depart, str) or not depart.strip():
        raise ValidationErreur("Date de départ manquante")

    try:
        dt = datetime.fromisoformat(
            depart.strip().replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValidationErreur(
            "Date de départ illisible"
        ) from exc

    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValidationErreur(
            "Départ sans fuseau horaire"
        )

    try:
        depart_utc = dt.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Décalage horaire invalide"
        ) from exc

    maintenant = datetime.now(timezone.utc)

    if depart_utc <= maintenant:
        raise ValidationErreur(
            "Départ déjà passé : pas de nouveau FIGÉ"
        )

    if depart_utc - maintenant > MAX_AVANCE_DEPART:
        raise ValidationErreur(
            "Départ trop éloigné : vérification nécessaire"
        )

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise ValidationErreur(
            "Liste des partants absente"
        )

    vus: set[int] = set()
    actifs: set[int] = set()
    non_partants_reels: set[int] = set()

    for cheval in partants:
        if not isinstance(cheval, dict):
            raise ValidationErreur("Partant invalide")

        numero = _numero(
            cheval.get("numero"), "Partant"
        )

        if numero in vus:
            raise ValidationErreur(
                "Numéro de partant en double"
            )

        nom = cheval.get("nom")

        if not isinstance(nom, str) or not nom.strip():
            raise ValidationErreur(
                "Nom de cheval absent"
            )

        if type(cheval.get("non_partant")) is not bool:
            raise ValidationErreur(
                "Statut non-partant invalide"
            )

        vus.add(numero)

        if cheval["non_partant"]:
            non_partants_reels.add(numero)
        else:
            actifs.add(numero)

    if "nombre_partants" in course:
        nombre = course["nombre_partants"]

        if type(nombre) is not int or nombre != len(actifs):
            raise ValidationErreur(
                "Nombre de partants actifs incohérent"
            )

    if "non_partants" in course:
        liste_np = course["non_partants"]

        if not isinstance(liste_np, list):
            raise ValidationErreur(
                "Liste non_partants invalide"
            )

        numeros_np = [
            _numero(n, "Non-partant")
            for n in liste_np
        ]

        if len(numeros_np) != len(set(numeros_np)):
            raise ValidationErreur(
                "Non-partant en double"
            )

        if set(numeros_np) != non_partants_reels:
            raise ValidationErreur(
                "Liste des non-partants incohérente"
            )

    if len(actifs) < 5:
        raise ValidationErreur(
            "Moins de cinq partants actifs"
        )

    return actifs


def valider_prediction(
    moteur: str,
    positions: Any,
    actifs: set[int]
) -> list[int]:
    """Vérifie cinq positions distinctes et actives."""

    if moteur not in MOTEURS:
        raise ValidationErreur("Moteur inconnu")

    if (
        not isinstance(actifs, set)
        or any(
            type(n) is not int or n <= 0
            for n in actifs
        )
    ):
        raise ValidationErreur(
            "Ensemble de partants actifs invalide"
        )

    if not isinstance(positions, list) or len(positions) != 5:
        raise ValidationErreur(
            f"{moteur}: cinq positions exigées"
        )

    if any(
        type(n) is not int or n <= 0
        for n in positions
    ):
        raise ValidationErreur(
            f"{moteur}: numéros entiers positifs exigés"
        )

    if (
        len(set(positions)) != 5
        or not set(positions).issubset(actifs)
    ):
        raise ValidationErreur(
            f"{moteur}: doublon ou cheval non-partant/inconnu"
        )

    return positions.copy()
