#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression de la coordination centrale X1000."""

import copy
import unittest
from unittest.mock import patch

import coordination_x1000 as central
import integration_x1000 as integration

from validation_moteurs import ValidationErreur


NOMS = ("M1", "M2", "M3", "M4", "M5")


def jeu_valide():
    course = integration.creer_course_test()
    moteurs = integration.charger_moteurs()

    sorties = {
        nom: copy.deepcopy(
            moteur.analyser_course(
                copy.deepcopy(course)
            )
        )
        for nom, moteur in moteurs.items()
    }

    return course, sorties


class TestCoordinationCentrale(unittest.TestCase):

    def setUp(self):
        self.course, self.sorties = jeu_valide()

    def test_01_coordination_complete(self):
        resultat = central.coordonner(
            self.course, self.sorties
        )
        self.assertTrue(
            resultat["coordination_complete"]
        )
        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE",
        )
        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(NOMS),
        )

    def test_02_classements_preserves(self):
        resultat = central.coordonner(
            self.course, self.sorties
        )
        for nom in NOMS:
            attendu = [
                p["numero"]
                for p in self.sorties[nom]["classement"]
            ]
            self.assertEqual(
                resultat["predictions_independantes"][nom],
                attendu,
            )

    def test_03_non_partant_exclu(self):
        resultat = central.coordonner(
            self.course, self.sorties
        )
        for positions in resultat[
            "predictions_independantes"
        ].values():
            self.assertNotIn(7, positions)

    def test_04_rejet_moteur_absent(self):
        sorties = copy.deepcopy(self.sorties)
        del sorties["M5"]
        with self.assertRaises(ValidationErreur):
            central.coordonner(self.course, sorties)

    def test_05_rejet_identite_fausse(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M2"]["moteur"] = "M1"
        with self.assertRaises(ValidationErreur):
            central.coordonner(self.course, sorties)

    def test_06_rejet_fige_publication(self):
        for champ in ("fige", "publication"):
            with self.subTest(champ=champ):
                sorties = copy.deepcopy(self.sorties)
                sorties["M3"][champ] = True
                with self.assertRaises(ValidationErreur):
                    central.coordonner(
                        self.course, sorties
                    )

    def test_07_rejet_doublon(self):
        sorties = copy.deepcopy(self.sorties)
        classement = sorties["M4"]["classement"]
        classement[1]["numero"] = classement[0]["numero"]
        with self.assertRaises(ValidationErreur):
            central.coordonner(self.course, sorties)

    def test_08_rejet_non_partant(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M1"]["classement"][0]["numero"] = 7
        with self.assertRaises(ValidationErreur):
            central.coordonner(self.course, sorties)

    def test_09_aucune_mutation_entrees(self):
        course_initiale = copy.deepcopy(self.course)
        sorties_initiales = copy.deepcopy(self.sorties)

        central.coordonner(self.course, self.sorties)

        self.assertEqual(self.course, course_initiale)
        self.assertEqual(self.sorties, sorties_initiales)

    def test_10_empreinte_stable(self):
        a = central.coordonner(
            self.course, self.sorties
        )
        b = central.coordonner(
            self.course, self.sorties
        )
        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"],
        )
        self.assertEqual(len(a["empreinte_sha256"]), 64)

    def test_11_empreinte_detecte_changement(self):
        a = central.coordonner(
            self.course, self.sorties
        )
        sorties = copy.deepcopy(self.sorties)
        positions = sorties["M1"]["classement"]
        positions[0], positions[1] = (
            positions[1], positions[0]
        )
        positions[0]["position_predite"] = 1
        positions[1]["position_predite"] = 2

        b = central.coordonner(self.course, sorties)

        self.assertNotEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"],
        )

    def test_12_protections(self):
        resultat = central.coordonner(
            self.course, self.sorties
        )
        for champ in (
            "publication_autorisee",
            "fige_officiel",
            "fige_automatique",
            "validation_officielle",
            "archives_modifiees",
        ):
            self.assertIs(resultat[champ], False)

    def test_13_integration_cinq_moteurs(self):
        resultat = integration.executer_integration(
            self.course
        )
        self.assertTrue(
            resultat["coordination_complete"]
        )
        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(NOMS),
        )

    def test_14_refus_course_passee(self):
        course = copy.deepcopy(self.course)
        course["depart"] = "2020-01-01T12:00:00Z"
        with self.assertRaises(ValidationErreur):
            central.coordonner(course, self.sorties)

    def test_15_lecture_seule(self):
        with patch(
            "builtins.open",
            side_effect=AssertionError(
                "Acces fichier interdit"
            ),
        ):
            resultat = central.coordonner(
                self.course, self.sorties
            )
        self.assertFalse(
            resultat["archives_modifiees"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
