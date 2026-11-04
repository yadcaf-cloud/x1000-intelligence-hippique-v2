"""Validation défensive des courses et des sorties M1-M5.

Ce module ne collecte aucune donnée, ne lance aucun moteur,
ne crée aucun FIGÉ et ne publie rien.

Les attestations reçues ne constituent pas
une vérification officielle indépendante.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


MOTEURS = tuple(f"M{i}" for i in range(1, 6))
MAX_AVANCE_DEPART = timedelta(days=30)

_ISO_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:[Zz]|[+-](?:0\d|1\d|2[0-3]):[0-5]\d)$"
)


class ValidationErreur(ValueError):
    """Donnée de course ou prédiction non conforme."""


def _numero(valeur: Any, contexte: str) -> int:
    """Accepte uniquement un entier strictement positif."""

    if type(valeur) is not int or valeur <= 0:
        raise ValidationErreur(
            f"{contexte}: numéro entier positif exigé"
        )

    return valeur


def _depart_utc(valeur: Any) -> datetime:
    """Convertit un horodatage ISO 8601 complet en UTC."""

    if not isinstance(valeur, str) or not valeur.strip():
        raise ValidationErreur("Date de départ manquante")

    texte = valeur.strip()

    if not _ISO_DEPART.fullmatch(texte):
        raise ValidationErreur(
            "Départ ISO 8601 complet avec fuseau exigé"
        )

    if texte.endswith(("Z", "z")):
        texte = texte[:-1] + "+00:00"

    try:
        depart = datetime.fromisoformat(texte)
        decalage = depart.utcoffset()

        if depart.tzinfo is None or decalage is None:
            raise ValidationErreur(
                "Départ sans fuseau horaire"
            )

        if not (
            -timedelta(hours=24)
            < decalage
            < timedelta(hours=24)
        ):
            raise ValidationErreur(
                "Décalage horaire invalide"
            )

        return depart.astimezone(timezone.utc)

    except (ValueError, OverflowError) as exc:
        if isinstance(exc, ValidationErreur):
            raise

        raise ValidationErreur(
            "Date ou décalage horaire invalide"
        ) from exc


def valider_course(course: dict[str, Any]) -> set[int]:
    """Valide une course future et retourne les numéros actifs.

    Les indicateurs de vérification sont des attestations
    externes. Ce module ne consulte aucune source officielle.
    """

    if not isinstance(course, dict):
        raise ValidationErreur("Course invalide")

    if course.get("localisation_france_verifiee") is not True:
        raise ValidationErreur(
            "Localisation France non vérifiée"
        )

    if course.get("depart_verifie") is not True:
        raise ValidationErreur("Départ non vérifié")

    depart_utc = _depart_utc(course.get("depart"))
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
            cheval.get("numero"),
            "Partant"
        )

        if numero in vus:
            raise ValidationErreur(
                "Numéro de partant en double"
            )

        nom = cheval.get("nom")

        if not isinstance(nom, str) or not nom.strip():
            raise ValidationErreur("Nom de cheval absent")

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
    actifs: set[int],
) -> list[int]:
    """Contrôle cinq positions distinctes et actives."""

    if type(moteur) is not str or moteur not in MOTEURS:
        raise ValidationErreur("Moteur inconnu")

    if (
        type(actifs) is not set
        or len(actifs) < 5
        or any(
            type(n) is not int or n <= 0
            for n in actifs
        )
    ):
        raise ValidationErreur(
            "Ensemble de partants actifs invalide"
        )

    if type(positions) is not list or len(positions) != 5:
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
