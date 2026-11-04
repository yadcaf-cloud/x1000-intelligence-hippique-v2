"""Validation défensive des courses et des sorties M1-M5.

Ce module ne collecte aucune donnée, ne lance aucun moteur,
ne crée aucun FIGÉ et ne publie rien.

Les attestations reçues ne constituent pas
une vérification officielle indépendante.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


MOTEURS = tuple(f"M{i}" for i in range(1, 6))

MAX_AVANCE_DEPART = timedelta(days=30)


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
    """Convertit un départ ISO 8601 horodaté en UTC."""

    if not isinstance(valeur, str) or not valeur.strip():
        raise ValidationErreur(
            "Date de départ manquante"
        )

    texte = valeur.strip()

    if texte.endswith(("Z", "z")):
        texte = texte[:-1] + "+00:00"

    try:
        depart = datetime.fromisoformat(texte)

    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Date de départ illisible"
        ) from exc

    if depart.tzinfo is None or depart.utcoffset() is None:
        raise ValidationErreur(
            "Départ sans fuseau horaire"
        )

    try:
        return depart.astimezone(timezone.utc)

    except (ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Décalage horaire invalide"
        ) from exc


def valider_course(course: dict[str, Any]) -> set[int]:
    """Valide une course future et retourne ses numéros actifs.

    Les indicateurs de vérification sont des attestations
    fournies en entrée.

    Cette fonction ne consulte pas elle-même
    les sources officielles.
    """

    if not isinstance(course, dict):
        raise ValidationErreur(
            "Course invalide"
        )

    # Vérification déclarée de la localisation française.
    if course.get("localisation_france_verifiee") is not True:
        raise ValidationErreur(
            "Localisation France non vérifiée"
        )

    # Vérification déclarée de l'horaire.
    if course.get("depart_verifie") is not True:
        raise ValidationErreur(
            "Départ non vérifié"
        )

    depart_utc = _depart_utc(
        course.get("depart")
    )

    maintenant = datetime.now(timezone.utc)

    # Aucun nouveau FIGÉ après départ.
    if depart_utc <= maintenant:
        raise ValidationErreur(
            "Départ déjà passé : pas de nouveau FIGÉ"
        )

    # Limite défensive de fraîcheur de la programmation.
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
            raise ValidationErreur(
                "Partant invalide"
            )

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

    # Cohérence du nombre déclaré de chevaux actifs.
    if "nombre_partants" in course:

        nombre = course["nombre_partants"]

        if type(nombre) is not int or nombre != len(actifs):
            raise ValidationErreur(
                "Nombre de partants actifs incohérent"
            )

    # Cohérence de la liste des non-partants.
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

    # Cinq chevaux actifs minimum pour un classement Top 5.
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
    """Vérifie cinq positions distinctes et actives.

    Cette fonction ne calcule pas de pronostic.
    Elle contrôle uniquement une sortie déjà produite.
    """

    # Identification stricte des cinq moteurs.
    if type(moteur) is not str or moteur not in MOTEURS:
        raise ValidationErreur(
            "Moteur inconnu"
        )

    # Ensemble des numéros actifs.
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

    # Cinq positions exactement.
    if type(positions) is not list or len(positions) != 5:
        raise ValidationErreur(
            f"{moteur}: cinq positions exigées"
        )

    # Numéros entiers strictement positifs.
    if any(
        type(n) is not int or n <= 0
        for n in positions
    ):
        raise ValidationErreur(
            f"{moteur}: numéros entiers positifs exigés"
        )

    # Aucun doublon ni cheval absent ou non partant.
    if (
        len(set(positions)) != 5
        or not set(positions).issubset(actifs)
    ):
        raise ValidationErreur(
            f"{moteur}: doublon ou cheval non-partant/inconnu"
        )

    # Copie indépendante de la liste d'origine.
    return positions.copy()
