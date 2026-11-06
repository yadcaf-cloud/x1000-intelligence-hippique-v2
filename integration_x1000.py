#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
INTEGRATION SECURISEE M1 A M5

- Cinq moteurs independants
- Validation des sorties par le noyau commun
- Conservation des classements originaux
- Coordination sans prediction inventee
- Empreinte SHA-256 reproductible
- Controle des non-partants
- Controle des donnees insuffisantes
- Controle des courses passees
- Aucun FIGE automatique
- Aucune collecte PMU automatique
- Aucune publication automatique
- Aucune modification des archives

Python 3.11 - Bibliotheque standard uniquement.
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


# ============================================================
# 1. EMPREINTE SHA-256 REPRODUCTIBLE
# ============================================================

def empreinte_sha256(donnees):
    """
    Calcule une empreinte reproductible.

    Exclut uniquement les horodatages analyse_a
    du calcul, sans modifier les donnees sources.

    Cette empreinte est une empreinte de contenu
    stable, pas une empreinte brute des archives.
    """

    def normaliser(valeur):

        if isinstance(valeur, dict):
            return {
                cle: normaliser(contenu)
                for cle, contenu in valeur.items()
                if cle != "analyse_a"
            }

        if isinstance(valeur, list):
            return [
                normaliser(element)
                for element in valeur
            ]

        return valeur

    donnees_stables = normaliser(donnees)

    contenu = json.dumps(
        donnees_stables,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


# ============================================================
# 2. CHARGEMENT DES CINQ MOTEURS
# ============================================================

def charger_moteurs():
    """
    Charge les cinq moteurs independamment.

    Controle identite, version et noyau.
    """

    moteurs = {}

    for nom in NOMS:

        module = importlib.import_module(
            f"moteurs.{nom.lower()}"
        )

        if getattr(module, "MOTEUR", None) != nom:
            raise ValidationErreur(
                f"Identite incorrecte : {nom}"
            )

        if str(
            getattr(module, "VERSION", None)
        ) != VERSION:
            raise ValidationErreur(
                f"Version incompatible : {nom}"
            )

        verifier = getattr(
            module,
            "verifier_noyau",
            None,
        )

        analyser = getattr(
            module,
            "analyser_course",
            None,
        )

        if not callable(verifier):
            raise ValidationErreur(
                f"{nom}: verification du noyau absente"
            )

        if not callable(analyser):
            raise ValidationErreur(
                f"{nom}: analyse indisponible"
            )

        verifier()

        moteurs[nom] = module

    return moteurs


# ============================================================
# 3. VALIDATION DES SORTIES
# ============================================================

def verifier_resultat(nom, resultat, course):
    """
    Controle la sortie d'un moteur.

    Ne modifie ni le resultat ni la course.
    """

    if nom not in NOMS:
        raise ValidationErreur(
            "Moteur inconnu"
        )

    if not isinstance(resultat, dict):
        raise ValidationErreur(
            f"{nom}: resultat invalide"
        )

    if resultat.get("moteur") != nom:
        raise ValidationErreur(
            f"{nom}: identite incoherente"
        )

    if str(resultat.get("version")) != VERSION:
        raise ValidationErreur(
            f"{nom}: version incompatible"
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


# ============================================================
# 4. EXTRACTION DES CLASSEMENTS
# ============================================================

def extraire_numeros(resultat):
    """
    Extrait les numeros sans changer leur ordre.
    """

    statut = resultat["statut"]

    if statut == "ANALYSE_DISPONIBLE":

        positions = resultat["classement"]

        if len(positions) != 5:
            raise ValidationErreur(
                "Cinq positions requises"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        positions = resultat[
            "classement_partiel"
        ]

    elif statut == "NON_ANALYSABLE":

        positions = []

    else:
        raise ValidationErreur(
            f"Statut inconnu : {statut}"
        )

    numeros = [
        position["numero"]
        for position in positions
    ]

    if len(numeros) != len(set(numeros)):
        raise ValidationErreur(
            "Classement contenant des doublons"
        )

    return numeros


# ============================================================
# 5. COORDINATION CENTRALE
# ============================================================

def coordonner(course, sorties):
    """
    Coordonne les cinq sorties deja calculees.

    Aucun consensus artificiel.
    Aucune modification des classements.
    Aucun FIGE ou publication.
    """

    if not isinstance(course, dict):
        raise ValidationErreur(
            "Course invalide"
        )

    valider_course(course)

    valide, raison = (
        noyau_commun.verifier_course(course)
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
        "nombre_moteurs": len(NOMS),
        "moteurs_complets": [
            nom
            for nom in NOMS
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


# ============================================================
# 6. EXECUTION INDEPENDANTE M1 A M5
# ============================================================

def executer_integration(course):
    """
    Execute les cinq moteurs separement.

    Chaque moteur recoit une copie independante.
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


# ============================================================
# 7. CREATION D'UNE COURSE FICTIVE
# ============================================================

def creer_course_test():
    """
    Course fictive exclusivement pour les tests.

    Aucune donnee PMU reelle.
    Aucun pronostic officiel.
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


# ============================================================
# 8. AUTOTEST COMPLET
# ============================================================

def self_test():
    """
    Verifie :
    - Les cinq moteurs
    - Les classements independants
    - Les non-partants
    - La reproductibilite SHA-256
    - Les donnees insuffisantes
    - Le refus des courses passees
    - Les protections FIGE et archives
    """

    course = creer_course_test()

    original = copy.deepcopy(course)

    premier = executer_integration(
        course
    )

    second = executer_integration(
        course
    )

    assert course == original, (
        "Course originale modifiee"
    )

    assert premier[
        "coordination_complete"
    ], "Coordination incomplete"

    assert premier[
        "nombre_moteurs"
    ] == 5, "Nombre de moteurs incorrect"

    assert set(
        premier["predictions_independantes"]
    ) == set(NOMS), (
        "Predictions M1-M5 incompletes"
    )

    for nom, classement in premier[
        "predictions_independantes"
    ].items():

        assert len(classement) == 5, nom

        assert len(set(classement)) == 5, nom

        assert 7 not in classement, (
            f"{nom}: non-partant classe"
        )

    assert (
        premier["empreinte_sha256"]
        == second["empreinte_sha256"]
    ), "Empreintes SHA-256 differentes"

    assert len(
        premier["empreinte_sha256"]
    ) == 64, "Empreinte SHA-256 invalide"

    # Controle de l'independance des copies.

    assert (
        premier["analyses_independantes"]
        is not second["analyses_independantes"]
    ), "Analyses non independantes"

    # Verification des protections.

    for champ in (
        "publication_autorisee",
        "fige_officiel",
        "fige_automatique",
        "validation_officielle",
        "archives_modifiees",
    ):

        assert premier[champ] is False, (
            f"Protection inactive : {champ}"
        )

    # Test des donnees insuffisantes.

    course_incomplete = creer_course_test()

    moteurs = charger_moteurs()

    champ_m5 = moteurs["M5"].CHAMP

    for cheval in course_incomplete["partants"]:

        cheval.pop(
            champ_m5,
            None,
        )

    partiel = executer_integration(
        course_incomplete
    )

    assert not partiel[
        "coordination_complete"
    ], "Course incomplete acceptee"

    assert "M5" in partiel[
        "moteurs_incomplets"
    ], "M5 non detecte comme incomplet"

    assert partiel[
        "predictions_independantes"
    ] == {}, (
        "Predictions completes publiees "
        "malgre les donnees insuffisantes"
    )

    # Test du refus des courses passees.

    course_passee = creer_course_test()

    depart_passe = (
        datetime.now(timezone.utc)
        - timedelta(days=1)
    )

    course_passee["depart"] = (
        depart_passe.isoformat()
    )

    course_passee["id"] = (
        depart_passe.astimezone(
            ZoneInfo("Europe/Paris")
        ).strftime("%Y-%m-%d")
        + "-R1-C1"
    )

    try:
        executer_integration(
            course_passee
        )

    except (ValidationErreur, ValueError):
        pass

    else:
        raise AssertionError(
            "Course passee acceptee"
        )

    # Verification SHA-256 sur horodatages.

    donnees_a = {
        "moteur": "M1",
        "analyse_a": "2026-01-01T10:00:00Z",
        "classement": [1, 2, 3, 4, 5],
    }

    donnees_b = {
        "moteur": "M1",
        "analyse_a": "2026-01-01T11:00:00Z",
        "classement": [1, 2, 3, 4, 5],
    }

    assert (
        empreinte_sha256(donnees_a)
        == empreinte_sha256(donnees_b)
    ), "Horodatage affecte l'empreinte"

    donnees_c = copy.deepcopy(donnees_b)

    donnees_c["classement"] = [
        5, 4, 3, 2, 1
    ]

    assert (
        empreinte_sha256(donnees_a)
        != empreinte_sha256(donnees_c)
    ), "Changement sportif non detecte"

    print("================================")
    print("X1000 - INTEGRATION M1 A M5")
    print("================================")
    print("SELF-TEST : OK")
    print("Cinq moteurs : OK")
    print("Coordination : OK")
    print("Independance : OK")
    print("Classements : OK")
    print("Non-partants : OK")
    print("Reproductibilite SHA-256 : OK")
    print("Donnees insuffisantes : OK")
    print("Course passee refusee : OK")
    print("FIGE automatique : NON")
    print("Collecte PMU : NON")
    print("Publication : NON")
    print("Archives modifiees : NON")
    print("================================")


# ============================================================
# 9. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    self_test()
