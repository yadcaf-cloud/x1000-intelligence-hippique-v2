#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Tests renforces de coordination centrale.

Aucune collecte PMU.
Aucune execution sportive M1-M5.
Aucun FIGE ni publication.
Aucune modification des archives.
"""

import copy
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import coordination_x1000 as central
from validation_moteurs import ValidationErreur


MOTEURS = ("M1", "M2", "M3", "M4", "M5")

PROTECTIONS = (
    "publication_autorisee",
    "fige_officiel",
    "fige_automatique",
    "validation_officielle",
    "archives_modifiees",
)


def creer_course():
    depart = datetime.now(timezone.utc) + timedelta(days=2)

    return {
        "id": depart.strftime("%Y-%m-%d") + "-R1-C1",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart.isoformat(),
        "nombre_partants": 6,
        "partants": [
            {
                "numero": numero,
                "nom": f"TEST_{numero}",
                "non_partant": numero == 7,
            }
            for numero in range(1, 8)
        ],
        "non_partants": [7],
    }


def creer_sorties():
    return {
        moteur: [
            ((position + index - 1) % 6) + 1
            for position in range(1, 6)
        ]
        for index, moteur in enumerate(MOTEURS)
    }


class TestCoordinationRenforcee(unittest.TestCase):

    def setUp(self):
        self.course = creer_course()
        self.sorties = creer_sorties()
        self.course_originale = copy.deepcopy(self.course)
        self.sorties_originales = copy.deepcopy(self.sorties)

    def coordonner(self, sorties=None, course=None):
        # Isolation du controle du noyau :
        # les validations reelles de validation_moteurs
        # restent actives.
        with patch.object(
            central.noyau_commun,
            "verifier_course",
            return_value=(True, "TEST"),
        ):
            return central.coordonner(
                self.course if course is None else course,
                self.sorties if sorties is None else sorties,
            )

    def test_cinq_moteurs(self):
        resultat = self.coordonner()
        self.assertEqual(resultat["nombre_moteurs"], 5)
        self.assertTrue(resultat["coordination_complete"])
        self.assertEqual(
            set(resultat["moteurs_complets"]),
            set(MOTEURS),
        )

    def test_classements_independants(self):
        resultat = self.coordonner()
        predictions = resultat["predictions_independantes"]

        for moteur in MOTEURS:
            self.assertEqual(
                predictions[moteur],
                self.sorties[moteur],
            )

    def test_statut_non_publie(self):
        resultat = self.coordonner()
        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE",
        )

        for protection in PROTECTIONS:
            self.assertIs(resultat[protection], False)

    def test_non_partant_refuse(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M3"] = [1, 2, 3, 4, 7]

        with self.assertRaises(ValidationErreur):
            self.coordonner(sorties=sorties)

    def test_doublon_refuse(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M2"] = [1, 1, 2, 3, 4]

        with self.assertRaises(ValidationErreur):
            self.coordonner(sorties=sorties)

    def test_moteur_manquant_refuse(self):
        sorties = copy.deepcopy(self.sorties)
        del sorties["M5"]

        with self.assertRaises(ValidationErreur):
            self.coordonner(sorties=sorties)

    def test_moteur_inconnu_refuse(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M6"] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValidationErreur):
            self.coordonner(sorties=sorties)

    def test_aucune_mutation(self):
        self.coordonner()
        self.assertEqual(self.course, self.course_originale)
        self.assertEqual(self.sorties, self.sorties_originales)

    def test_empreinte_sha256(self):
        resultat = self.coordonner()
        empreinte = resultat["empreinte_sha256"]

        self.assertRegex(empreinte, r"^[a-f0-9]{64}$")

        resultat_bis = self.coordonner()
        self.assertEqual(
            empreinte,
            resultat_bis["empreinte_sha256"],
        )

    def test_changement_classement_detecte(self):
        premier = self.coordonner()

        sorties = copy.deepcopy(self.sorties)
        sorties["M1"] = list(reversed(sorties["M1"]))

        second = self.coordonner(sorties=sorties)

        self.assertNotEqual(
            premier["empreinte_sha256"],
            second["empreinte_sha256"],
        )

    def test_course_passee_refusee(self):
        course = copy.deepcopy(self.course)
        course["depart"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()

        with self.assertRaises(ValidationErreur):
            self.coordonner(course=course)

    def test_attestation_france_obligatoire(self):
        course = copy.deepcopy(self.course)
        course["localisation_france_verifiee"] = False

        with self.assertRaises(ValidationErreur):
            self.coordonner(course=course)

    def test_alias_compatibilite(self):
        with patch.object(
            central.noyau_commun,
            "verifier_course",
            return_value=(True, "TEST"),
        ):
            resultat = central.coordonner_predictions(
                self.course,
                self.sorties,
            )

        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE",
        )

    def test_resultat_independant_des_entrees(self):
        resultat = self.coordonner()

        resultat["predictions_independantes"]["M1"][0] = 99

        self.assertEqual(
            self.sorties,
            self.sorties_originales,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
