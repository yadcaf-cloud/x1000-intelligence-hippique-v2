#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Tests renforces integration M1-M5 et coordination.

Tests fictifs exclusivement.
Aucune collecte PMU.
Aucun FIGE automatique.
Aucune publication.
Aucune modification des archives.
"""

import copy
import unittest
from unittest.mock import patch

import integration_x1000 as integration
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


class TestSecuriteIntegrationX1000(unittest.TestCase):

    def setUp(self):
        self.course = integration.creer_course_test()
        self.original = copy.deepcopy(self.course)

    def sorties(self):
        moteurs = integration.charger_moteurs()
        return {
            nom: moteurs[nom].analyser_course(
                copy.deepcopy(self.course)
            )
            for nom in MOTEURS
        }

    def verifier_protections(self, resultat):
        for cle in PROTECTIONS:
            self.assertIs(
                resultat[cle],
                False,
                f"Protection inactive : {cle}"
            )

    def test_01_cinq_moteurs(self):
        self.assertEqual(
            set(integration.charger_moteurs()),
            set(MOTEURS)
        )

    def test_02_sorties_valides(self):
        for nom, sortie in self.sorties().items():
            with self.subTest(moteur=nom):
                integration.verifier_resultat(
                    nom, sortie, self.course
                )

    def test_03_integration_complete(self):
        resultat = integration.executer_integration(
            copy.deepcopy(self.course)
        )
        self.assertEqual(resultat["nombre_moteurs"], 5)
        self.assertTrue(resultat["coordination_complete"])
        self.verifier_protections(resultat)

    def test_04_centrale_complete(self):
        resultat = central.coordonner(
            self.course, self.sorties()
        )
        self.assertEqual(resultat["nombre_moteurs"], 5)
        self.assertTrue(resultat["coordination_complete"])
        self.verifier_protections(resultat)

    def test_05_accord_classements(self):
        sorties = self.sorties()
        a = integration.coordonner(
            self.course, copy.deepcopy(sorties)
        )
        b = central.coordonner(
            self.course, copy.deepcopy(sorties)
        )
        self.assertEqual(
            a["predictions_independantes"],
            b["predictions_independantes"]
        )

    def test_06_non_partants_exclus(self):
        resultat = integration.executer_integration(
            self.course
        )
        for classement in result at_classements(resultat):
            self.assertNotIn(7, classement)

    def test_07_moteur_manquant(self):
        sorties = self.sorties()
        del sorties["M5"]
        for coordonner in (
            integration.coordonner,
            central.coordonner,
        ):
            with self.subTest(fonction=coordonner.__module__):
                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_08_identite_falsifiee(self):
        sorties = self.sorties()
        sorties["M1"]["moteur"] = "M5"
        for coordonner in (
            integration.coordonner,
            central.coordonner,
        ):
            with self.subTest(fonction=coordonner.__module__):
                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_09_fige_interdit(self):
        sorties = self.sorties()
        sorties["M2"]["fige"] = True
        for coordonner in (
            integration.coordonner,
            central.coordonner,
        ):
            with self.subTest(fonction=coordonner.__module__):
                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_10_publication_interdite(self):
        sorties = self.sorties()
        sorties["M4"]["publication"] = True
        for coordonner in (
            integration.coordonner,
            central.coordonner,
        ):
            with self.subTest(fonction=coordonner.__module__):
                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_11_course_non_modifiee(self):
        integration.executer_integration(self.course)
        self.assertEqual(self.course, self.original)

    def test_12_sorties_non_modifiees(self):
        sorties = self.sorties()
        original = copy.deepcopy(sorties)
        integration.coordonner(self.course, sorties)
        central.coordonner(self.course, sorties)
        self.assertEqual(sorties, original)

    def test_13_sha_stable_integration(self):
        a = integration.executer_integration(self.course)
        b = integration.executer_integration(self.course)
        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"]
        )

    def test_14_sha_detecte_changement(self):
        a = {"classement": [1, 2, 3, 4, 5]}
        b = {"classement": [2, 1, 3, 4, 5]}
        self.assertNotEqual(
            integration.empreinte_sha256(a),
            integration.empreinte_sha256(b)
        )

    def test_15_panne_moteur(self):
        moteurs = integration.charger_moteurs()
        with patch.object(
            moteurs["M3"],
            "analyser_course",
            side_effect=RuntimeError("PANNE_TEST_M3")
        ):
            with patch.object(
                integration,
                "charger_moteurs",
                return_value=moteurs
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "PANNE_TEST_M3"
                ):
                    integration.executer_integration(
                        self.course
                    )
        self.assertEqual(self.course, self.original)

    def test_16_empreinte_centrale(self):
        sorties = self.sorties()
        a = central.coordonner(self.course, sorties)
        b = central.coordonner(self.course, sorties)
        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"]
        )

    def test_17_protections_deux_systemes(self):
        sorties = self.sorties()
        for resultat in (
            integration.coordonner(self.course, sorties),
            central.coordonner(self.course, sorties),
        ):
            self.verifier_protections(resultat)

    def test_18_aucune_prediction_inventee(self):
        sorties = self.sorties()
        resultat = central.coordonner(self.course, sorties)
        for nom in MOTEURS:
            attendu = [
                p["numero"]
                for p in sorties[nom]["classement"]
            ]
            self.assertEqual(
                resultat["predictions_independantes"][nom],
                attendu
            )


def result_at_classements(resultat):
    return resultat["predictions_independantes"].values()


if __name__ == "__main__":
    unittest.main(verbosity=2)
