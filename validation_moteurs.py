#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.5 - VALIDATION SECURISEE DES MOTEURS M1 A M5

Fonctions :
- Validation defensive des courses PMU en France.
- Controle des dates de depart et des fuseaux.
- Controle des partants et non-partants.
- Controle des identifiants de course si presents.
- Validation des cinq positions de chaque moteur.
- Protection contre les doublons et types invalides.
- Verification des attestations externes requises.

Garanties :
- Aucune collecte PMU.
- Aucun acces reseau.
- Aucune execution des moteurs.
- Aucune publication automatique.
- Aucun FIGE automatique ou retroactif.
- Aucune modification des archives.
- Aucune ecriture dans les fichiers.
- Aucune donnee sportive inventee.

IMPORTANT :
Les attestations fournies ne constituent pas
une verification officielle independante.

Interfaces conservees :
    valider_course(course) -> set[int]
    valider_prediction(moteur, positions, actifs) -> list[int]

Python 3.10 ou superieur.
Bibliotheque standard uniquement.
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

MOTEURS = tuple(
    f"M{i}" for i in range(1, 6)
)

MAX_AVANCE_DEPART = timedelta(days=30)

NOMBRE_POSITIONS = 5

MIN_PARTANTS_ACTIFS = 5


_ISO_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"T\d{2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:[Zz]|[+-](?:0\d|1\d|2[0-3]):[0-5]\d)$"
)

_ID_COURSE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-R([1-9]\d*)-C([1-9]\d*)$"
)


# ============================================================
# EXCEPTION
# ============================================================

class ValidationErreur(ValueError):
    """Erreur de validation des donnees X1000."""


# ============================================================
# VALIDATION DES NUMEROS
# ============================================================

def _numero(
    valeur: Any,
    contexte: str,
) -> int:
    """
    Accepte uniquement un entier strictement positif.

    Les booleens sont rejetes.
    Les nombres flottants sont rejetes.
    Les chaines numeriques sont rejetees.
    """

    if type(valeur) is not int:
        raise ValidationErreur(
            f"{contexte}: entier strictement positif exige"
        )

    if valeur <= 0:
        raise ValidationErreur(
            f"{contexte}: numero strictement positif exige"
        )

    return valeur


# ============================================================
# VALIDATION DES DATES
# ============================================================

def _depart_utc(valeur: Any) -> datetime:
    """
    Convertit une date ISO 8601 explicite en UTC.

    Exemples :
        2026-11-05T14:30:00+01:00
        2026-11-05T13:30:00Z

    Une date sans fuseau est refusee.
    """

    if type(valeur) is not str:
        raise ValidationErreur(
            "Date de depart absente ou invalide"
        )

    texte = valeur.strip()

    if not texte:
        raise ValidationErreur(
            "Date de depart manquante"
        )

    if not _ISO_DEPART.fullmatch(texte):
        raise ValidationErreur(
            "Depart ISO 8601 avec fuseau explicite exige"
        )

    if texte[-1] in "Zz":
        texte = texte[:-1] + "+00:00"

    try:
        depart = datetime.fromisoformat(texte)

        decalage = depart.utcoffset()

        if decalage is None:
            raise ValidationErreur(
                "Fuseau horaire obligatoire"
            )

        if not (
            -timedelta(hours=24)
            < decalage
            < timedelta(hours=24)
        ):
            raise ValidationErreur(
                "Decalage horaire invalide"
            )

        return depart.astimezone(timezone.utc)

    except ValidationErreur:
        raise

    except (ValueError, OverflowError) as exc:
        raise ValidationErreur(
            "Date de depart invalide"
        ) from exc


# ============================================================
# IDENTIFIANT DE COURSE
# ============================================================

def _valider_identifiant_course(
    course: dict[str, Any],
    depart: datetime,
) -> None:
    """
    Controle l'identifiant lorsqu'il est fourni.

    Format :
        AAAA-MM-JJ-Rn-Cn

    La date est comparee dans le fuseau Europe/Paris.
    """

    identifiant = course.get(
        "course_id",
        course.get("id"),
    )

    if identifiant is None:
        return

    if type(identifiant) is not str:
        raise ValidationErreur(
            "Identifiant de course invalide"
        )

    correspondance = _ID_COURSE.fullmatch(
        identifiant
    )

    if correspondance is None:
        raise ValidationErreur(
            "Format identifiant de course invalide"
        )

    date_texte = correspondance.group(1)

    try:
        date_identifiant = datetime.strptime(
            date_texte,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValidationErreur(
            "Date de l'identifiant invalide"
        ) from exc

    try:
        from zoneinfo import ZoneInfo

        date_locale = depart.astimezone(
            ZoneInfo("Europe/Paris")
        ).date()

    except (ImportError, KeyError) as exc:
        raise ValidationErreur(
            "Fuseau Europe/Paris indisponible"
        ) from exc

    if date_identifiant != date_locale:
        raise ValidationErreur(
            "Date identifiant et depart incoherentes"
        )


# ============================================================
# VALIDATION DES ATTESTATIONS
# ============================================================

def _valider_attestations(
    course: dict[str, Any],
) -> None:
    """
    Verifie uniquement les attestations transmises.

    Cette fonction ne consulte aucune source officielle.
    """

    if (
        course.get("localisation_france_verifiee")
        is not True
    ):
        raise ValidationErreur(
            "Localisation France non attestee"
        )

    if course.get("depart_verifie") is not True:
        raise ValidationErreur(
            "Depart non atteste"
        )


# ============================================================
# VALIDATION DES PARTANTS
# ============================================================

def _valider_partants(
    course: dict[str, Any],
) -> set[int]:
    """
    Retourne l'ensemble des numeros actifs.

    Controle :
    - Liste valide.
    - Numeros entiers positifs.
    - Absence de doublons.
    - Noms non vides.
    - Statuts non_partant booleens.
    - Coherence des non-partants.
    - Coherence du nombre de partants actifs.
    """

    partants = course.get("partants")

    if type(partants) is not list:
        raise ValidationErreur(
            "Liste des partants absente ou invalide"
        )

    vus: set[int] = set()
    actifs: set[int] = set()
    non_partants_reels: set[int] = set()

    for index, cheval in enumerate(
        partants,
        start=1,
    ):

        if type(cheval) is not dict:
            raise ValidationErreur(
                f"Fiche partant {index} invalide"
            )

        numero = _numero(
            cheval.get("numero"),
            f"Partant {index}",
        )

        if numero in vus:
            raise ValidationErreur(
                f"Numero de partant en double: {numero}"
            )

        nom = cheval.get("nom")

        if (
            type(nom) is not str
            or not nom.strip()
        ):
            raise ValidationErreur(
                f"Nom absent pour le numero {numero}"
            )

        statut = cheval.get("non_partant")

        if type(statut) is not bool:
            raise ValidationErreur(
                f"Statut non_partant invalide: {numero}"
            )

        vus.add(numero)

        if statut:
            non_partants_reels.add(numero)
        else:
            actifs.add(numero)

    # Contrat X1000 :
    # nombre_partants correspond aux chevaux actifs.

    if "nombre_partants" in course:

        nombre = course["nombre_partants"]

        if type(nombre) is not int:
            raise ValidationErreur(
                "nombre_partants doit etre un entier"
            )

        if nombre != len(actifs):
            raise ValidationErreur(
                "Nombre de partants actifs incoherent"
            )

    # Verification de la liste globale des non-partants.

    if "non_partants" in course:

        liste_np = course["non_partants"]

        if type(liste_np) is not list:
            raise ValidationErreur(
                "Liste non_partants invalide"
            )

        numeros_np = [
            _numero(n, "Non-partant")
            for n in liste_np
        ]

        if len(numeros_np) != len(
            set(numeros_np)
        ):
            raise ValidationErreur(
                "Numero non-partant en double"
            )

        if set(numeros_np) != non_partants_reels:
            raise ValidationErreur(
                "Liste des non-partants incoherente"
            )

    if len(actifs) < MIN_PARTANTS_ACTIFS:
        raise ValidationErreur(
            "Moins de cinq partants actifs"
        )

    return actifs


# ============================================================
# VALIDATION COMPLETE D'UNE COURSE
# ============================================================

def valider_course(
    course: dict[str, Any],
) -> set[int]:
    """
    Valide une course future et retourne ses numeros actifs.

    Cette validation reste locale et defensive.

    Elle ne certifie pas l'exactitude sportive
    des informations transmises.
    """

    if type(course) is not dict:
        raise ValidationErreur(
            "Course invalide"
        )

    # 1. Attestations obligatoires.

    _valider_attestations(course)

    # 2. Date et fuseau horaire.

    depart = _depart_utc(
        course.get("depart")
    )

    maintenant = datetime.now(
        timezone.utc
    )

    if depart <= maintenant:
        raise ValidationErreur(
            "Depart deja passe"
        )

    if (
        depart - maintenant
        > MAX_AVANCE_DEPART
    ):
        raise ValidationErreur(
            "Depart a plus de 30 jours"
        )

    # 3. Identifiant facultatif.

    _valider_identifiant_course(
        course,
        depart,
    )

    # 4. Partants et non-partants.

    actifs = _valider_partants(
        course
    )

    # 5. Retour d'une copie independante.

    return set(actifs)


# ============================================================
# VALIDATION D'UNE PREDICTION MOTEUR
# ============================================================

def valider_prediction(
    moteur: str,
    positions: Any,
    actifs: set[int],
) -> list[int]:
    """
    Valide les cinq positions d'un moteur M1 a M5.

    Regles :
    - Moteur reconnu.
    - Ensemble de partants actifs valide.
    - Exactement cinq positions.
    - Numeros entiers strictement positifs.
    - Aucun doublon.
    - Tous les chevaux doivent etre actifs.

    Retourne une copie independante des positions.
    """

    # 1. Controle du moteur.

    if (
        type(moteur) is not str
        or moteur not in MOTEURS
    ):
        raise ValidationErreur(
            "Moteur inconnu"
        )

    # 2. Controle des partants actifs.

    if type(actifs) is not set:
        raise ValidationErreur(
            "Ensemble des partants actifs invalide"
        )

    if len(actifs) < MIN_PARTANTS_ACTIFS:
        raise ValidationErreur(
            "Nombre insuffisant de partants actifs"
        )

    for numero in actifs:
        _numero(
            numero,
            "Partant actif",
        )

    # 3. Controle du classement.

    if type(positions) is not list:
        raise ValidationErreur(
            f"{moteur}: liste de positions exigee"
        )

    if len(positions) != NOMBRE_POSITIONS:
        raise ValidationErreur(
            f"{moteur}: exactement cinq positions exigees"
        )

    # 4. Controle des numeros.

    numeros = [
        _numero(
            valeur,
            f"{moteur}: position {index}",
        )
        for index, valeur in enumerate(
            positions,
            start=1,
        )
    ]

    # 5. Controle des doublons.

    if len(set(numeros)) != NOMBRE_POSITIONS:
        raise ValidationErreur(
            f"{moteur}: doublon dans les positions"
        )

    # 6. Controle des chevaux actifs.

    inconnus = set(numeros) - actifs

    if inconnus:
        raise ValidationErreur(
            f"{moteur}: cheval absent des actifs"
        )

    # 7. Retour d'une copie.

    return numeros.copy()


# ============================================================
# VALIDATION GROUPEE DES CINQ MOTEURS
# ============================================================

def valider_predictions_moteurs(
    predictions: dict[str, Any],
    actifs: set[int],
    exiger_cinq_moteurs: bool = True,
) -> dict[str, list[int]]:
    """
    Valide plusieurs predictions independantes.

    Format :
        {
            "M1": [1, 2, 3, 4, 5],
            "M2": [2, 3, 4, 5, 6],
            ...
        }

    Par defaut, les cinq moteurs sont obligatoires.

    Aucun arbitrage central n'est effectue.
    Aucun classement n'est modifie.
    """

    if type(predictions) is not dict:
        raise ValidationErreur(
            "Predictions moteurs invalides"
        )

    moteurs_recus = set(
        predictions.keys()
    )

    moteurs_attendus = set(
        MOTEURS
    )

    inconnus = (
        moteurs_recus - moteurs_attendus
    )

    if inconnus:
        raise ValidationErreur(
            "Presence de moteurs inconnus"
        )

    if exiger_cinq_moteurs:

        if moteurs_recus != moteurs_attendus:
            raise ValidationErreur(
                "Predictions M1 a M5 incompletes"
            )

    resultats: dict[str, list[int]] = {}

    for moteur in MOTEURS:

        if moteur not in predictions:
            continue

        resultats[moteur] = valider_prediction(
            moteur,
            predictions[moteur],
            actifs,
        )

    return resultats


# ============================================================
# AUTO-TEST LOCAL
# ============================================================

def _self_test() -> bool:
    """
    Tests locaux sans collecte ni ecriture.

    Ne remplace pas une suite de tests de regression.
    """

    depart_futur = (
        datetime.now(timezone.utc)
        + timedelta(days=1)
    )

    depart_texte = depart_futur.isoformat()

    course = {
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart_texte,
        "nombre_partants": 6,
        "partants": [
            {
                "numero": n,
                "nom": f"Cheval {n}",
                "non_partant": False,
            }
            for n in range(1, 7)
        ],
        "non_partants": [],
    }

    actifs = valider_course(
        course
    )

    assert actifs == {
        1, 2, 3, 4, 5, 6
    }

    predictions = {
        "M1": [1, 2, 3, 4, 5],
        "M2": [2, 3, 4, 5, 6],
        "M3": [3, 4, 5, 6, 1],
        "M4": [4, 5, 6, 1, 2],
        "M5": [5, 6, 1, 2, 3],
    }

    resultats = valider_predictions_moteurs(
        predictions,
        actifs,
    )

    assert len(resultats) == 5

    for moteur in MOTEURS:
        assert len(resultats[moteur]) == 5

    # Rejet d'un doublon.

    try:
        valider_prediction(
            "M1",
            [1, 1, 2, 3, 4],
            actifs,
        )

    except ValidationErreur:
        pass

    else:
        raise AssertionError(
            "Doublon non detecte"
        )

    # Rejet d'un cheval inconnu.

    try:
        valider_prediction(
            "M2",
            [1, 2, 3, 4, 99],
            actifs,
        )

    except ValidationErreur:
        pass

    else:
        raise AssertionError(
            "Cheval inconnu non detecte"
        )

    # Rejet des booleens comme numeros.

    try:
        valider_prediction(
            "M3",
            [True, 2, 3, 4, 5],
            actifs,
        )

    except ValidationErreur:
        pass

    else:
        raise AssertionError(
            "Booleen non detecte"
        )

    # Rejet d'une course non attestee.

    course_invalide = course.copy()

    course_invalide[
        "depart_verifie"
    ] = False

    try:
        valider_course(
            course_invalide
        )

    except ValidationErreur:
        pass

    else:
        raise AssertionError(
            "Attestation invalide non detectee"
        )

    return True


# ============================================================
# EXECUTION DIRECTE
# ============================================================

def main() -> int:
    """
    Execute uniquement les tests locaux.

    Aucun moteur sportif n'est lance.
    Aucune donnee PMU n'est collectee.
    """

    try:
        _self_test()

        print(
            "X1000 V2.5 - VALIDATION MOTEURS"
        )

        print(
            "AUTO-TEST LOCAL : OK"
        )

        print(
            "MOTEURS : M1 M2 M3 M4 M5"
        )

        print(
            "COLLECTE PMU : DESACTIVEE"
        )

        print(
            "PUBLICATION : DESACTIVEE"
        )

        print(
            "FIGE AUTOMATIQUE : DESACTIVE"
        )

        print(
            "ECRITURE ARCHIVES : DESACTIVEE"
        )

        return 0

    except (
        ValidationErreur,
        AssertionError,
    ) as exc:

        print(
            f"ECHEC AUTO-TEST : {exc}"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
