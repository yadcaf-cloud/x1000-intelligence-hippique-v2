#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Integration securisee des moteurs M1 a M5.

- Cinq analyses independantes
- Validation des sorties par le noyau
- Conservation des classements
- Coordination sans prediction inventee
- Tracabilite SHA-256
- Aucun FIGE automatique
- Aucune collecte PMU
- Aucune publication
- Aucune ecriture d'archives

Bibliotheque standard Python uniquement.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from moteurs import noyau_commun
from validation_moteurs import (
    ValidationErreur,
    valider_course,
)


VERSION = "2.4"

NOMS = ("M1", "M2", "M3", "M4", "M5")

STATUT_COMPLET = "VALIDE_NON_PUBLIE"

STATUT_PARTIEL = (
    "COORDINATION_INCOMPLETE_NON_PUBLIE"
)


def empreinte_sha256(donnees):
    contenu = json.dumps(
        donnees,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


def charger_moteurs():
    moteurs = {}

    for nom in NOMS:
        module = importlib.import_module(
            f"moteurs.{nom.lower()}"
        )

        if module.MOTEUR != nom:
            raise ValidationErreur(
                f"Identite incorrecte : {nom}"
            )

        if str(module.VERSION) != VERSION:
            raise ValidationErreur(
                f"Version incompatible : {nom}"
            )

        module.verifier_noyau()

        moteurs[nom] = module

    return moteurs


def verifier_resultat(nom, resultat, course):
    if not isinstance(resultat, dict):
        raise ValidationErreur(
            f"{nom}: resultat invalide"
        )

    if resultat.get("moteur") != nom:
        raise ValidationErreur(
            f"{nom}: identite incoherente"
        )

    if resultat.get("fige") is not False:
        raise ValidationErreur(
            f"{nom}: FIGE interdit"
        )

    if resultat.get("publication") is not False:
        raise ValidationErreur(
            f"{nom}: publication interdite"
        )

    try:
        noyau_commun.verifier_sortie_analyse(
            resultat,
            course,
        )
    except (ValueError, TypeError) as exc:
        raise ValidationErreur(
            f"{nom}: sortie non conforme : {exc}"
        ) from exc

    return resultat


def extraire_numeros(resultat):
    statut = resultat["statut"]

    if statut == "ANALYSE_DISPONIBLE":
        positions = resultat["classement"]

        if len(positions) != 5:
            raise ValidationErreur(
                "Cinq positions requises"
            )

    elif statut == "DONNEES_INSUFFISANTES":
        positions = resultat["classement_partiel"]

    else:
        positions = []

    return [
        position["numero"]
        for position in positions
    ]


def coordonner(course, sorties):
    """
    Coordonne cinq sorties deja calculees.

    Ne modifie ni la course ni les sorties.
    Ne calcule pas de consensus artificiel.
    """

    if not isinstance(course, dict):
        raise ValidationErreur(
            "Course invalide"
        )

    valider_course(course)

    valide, raison = noyau_commun.verifier_course(
        course
    )

    if not valide:
        raise ValidationErreur(
            f"Course refusee : {raison}"
        )

    if not isinstance(sorties, dict):
        raise ValidationErreur(
            "Sorties invalides"
        )

    if set(sorties) != set(NOMS):
        raise ValidationErreur(
            "Les cinq moteurs sont obligatoires"
        )

    analyses = {}
    predictions = {}
    partiels = {}
    incomplets = []

    for nom in NOMS:
        resultat = verifier_resultat(
            nom,
            sorties[nom],
            course,
        )

        analyses[nom] = copy.deepcopy(
            resultat
        )

        numeros = extraire_numeros(
            resultat
        )

        if (
            resultat["statut"]
            == "ANALYSE_DISPONIBLE"
        ):
            predictions[nom] = numeros

        else:
            incomplets.append(nom)
            partiels[nom] = numeros

    complet = not incomplets

    statut = (
        STATUT_COMPLET
        if complet
        else STATUT_PARTIEL
    )

    donnees_trace = {
        "version": VERSION,
        "course": course,
        "analyses": analyses,
    }

    return {
        "version": VERSION,
        "course_id": course["id"],
        "statut": statut,
        "coordination_complete": complet,
        "nombre_moteurs": 5,
        "moteurs_complets": [
            nom for nom in NOMS
            if nom not in incomplets
        ],
        "moteurs_incomplets": incomplets,
        "analyses_independantes": analyses,
        "predictions_independantes": (
            predictions if complet else {}
        ),
        "predictions_partielles": partiels,
        "empreinte_sha256": empreinte_sha256(
            donnees_trace
        ),
        "publication_autorisee": False,
        "fige_officiel": False,
        "fige_automatique": False,
        "validation_officielle": False,
        "archives_modifiees": False,
    }


def executer_integration(course):
    """
    Execute M1 a M5 independamment.

    Chaque moteur recoit sa propre copie.
    Toute erreur interrompt la coordination.
    """

    moteurs = charger_moteurs()

    original = copy.deepcopy(course)
    sorties = {}

    for nom, moteur in moteurs.items():
        entree = copy.deepcopy(original)

        resultat = moteur.analyser_course(
            entree
        )

        if entree != original:
            raise ValidationErreur(
                f"{nom}: entree modifiee"
            )

        verifier_resultat(
            nom,
            resultat,
            original,
        )

        sorties[nom] = copy.deepcopy(
            resultat
        )

    return coordonner(
        original,
        sorties,
    )


def creer_course_test():
    """
    Course fictive pour test local.
    Aucune donnee sportive reelle.
    """

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    )

    date_france = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).strftime("%Y-%m-%d")

    moteurs = charger_moteurs()
    chevaux = []

    for numero in range(1, 8):
        cheval = {
            "numero": numero,
            "nom": f"TEST_{numero}",
            "non_partant": numero == 7,
        }

        for moteur in moteurs.values():
            cheval[moteur.CHAMP] = {
                critere: 90 - numero * 5
                for critere in moteur.POIDS
            }

        chevaux.append(cheval)

    return {
        "id": f"{date_france}-R1-C1",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart.isoformat(),
        "partants": chevaux,
        "nombre_partants": 6,
        "non_partants": [7],
    }


def self_test():
    course = creer_course_test()
    original = copy.deepcopy(course)

    premier = executer_integration(
        course
    )

    second = executer_integration(
        course
    )

    assert course == original

    assert premier["coordination_complete"]
    assert premier["nombre_moteurs"] == 5

    assert set(
        premier["predictions_independantes"]
    ) == set(NOMS)

    for nom, classement in premier[
        "predictions_independantes"
    ].items():
        assert len(classement) == 5, nom
        assert len(set(classement)) == 5
        assert 7 not in classement

    assert (
        premier["empreinte_sha256"]
        == second["empreinte_sha256"]
    )

    for champ in (
        "publication_autorisee",
        "fige_officiel",
        "fige_automatique",
        "validation_officielle",
        "archives_modifiees",
    ):
        assert premier[champ] is False

    course_incomplete = creer_course_test()

    for cheval in course_incomplete["partants"]:
        cheval.pop(
            charger_moteurs()["M5"].CHAMP,
            None,
        )

    partiel = executer_integration(
        course_incomplete
    )

    assert not partiel[
        "coordination_complete"
    ]

    assert "M5" in partiel[
        "moteurs_incomplets"
    ]

    assert partiel[
        "predictions_independantes"
    ] == {}

    course_passee = creer_course_test()
    course_passee["depart"] = (
        datetime.now(timezone.utc)
        - timedelta(days=1)
    ).isoformat()

    try:
        executer_integration(course_passee)
    except (ValidationErreur, ValueError):
        pass
    else:
        raise AssertionError(
            "Course passee acceptee"
        )

    print("X1000 - INTEGRATION M1 A M5")
    print("SELF-TEST : OK")
    print("Cinq moteurs : OK")
    print("Coordination : OK")
    print("Independance : OK")
    print("Classements : OK")
    print("Reproductibilite : OK")
    print("Donnees insuffisantes : OK")
    print("Course passee refusee : OK")
    print("FIGE automatique : NON")
    print("Publication : NON")
    print("Archives modifiees : NON")


if __name__ == "__main__":
    self_test()
