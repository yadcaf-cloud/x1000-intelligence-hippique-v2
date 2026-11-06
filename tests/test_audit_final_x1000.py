#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Audit final X1000 V2 - M1 a M5."""

import copy
import unittest
from unittest.mock import patch

import coordination_x1000 as central
import integration_x1000 as integration

from validation_moteurs import ValidationErreur


NOMS = ("M1", "M2", "M3", "M4", "M5")


class TestAuditFinalX1000(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.course = integration.creer_course_test()
        moteurs = integration.charger_moteurs()
        cls.sorties = {
            nom: moteur.analyser_course(
                copy.deepcopy(cls.course)
            )
            for nom, moteur in moteurs.items()
        }

    def coordonner(self, sorties=None):
        return central.coordonner(
            copy.deepcopy(self.course),
            copy.deepcopy(
                self.sorties if sorties is None else sorties
            ),
        )

    def test_cinq_moteurs(self):
        resultat = self.coordonner()
        self.assertTrue(resultat["coordination_complete"])
        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(NOMS),
        )

    def test_classements_preserves(self):
        resultat = self.coordonner()
        for nom in NOMS:
            attendu = [
                p["numero"]
                for p in self.sorties[nom]["classement"]
            ]
            self.assertEqual(
                resultat["predictions_independantes"][nom],
                attendu,
            )

    def test_aucun_non_partant(self):
        resultat = self.coordonner()
        for classement in resultat[
            "predictions_independantes"
        ].values():
            self.assertNotIn(7, classement)

    def test_aucune_mutation(self):
        course = copy.deepcopy(self.course)
        sorties = copy.deepcopy(self.sorties)
        sauvegarde = copy.deepcopy((course, sorties))

        central.coordonner(course, sorties)

        self.assertEqual(
            (course, sorties),
            sauvegarde,
        )

    def test_sha256_stable(self):
        a = self.coordonner()
        b = self.coordonner()
        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"],
        )

    def test_fige_publication_interdits(self):
        for nom in NOMS:
            for champ in ("fige", "publication"):
                with self.subTest(nom=nom, champ=champ):
                    sorties = copy.deepcopy(self.sorties)
                    sorties[nom][champ] = True
                    with self.assertRaises(ValidationErreur):
                        self.coordonner(sorties)

    def test_absence_moteur_refusee(self):
        sorties = copy.deepcopy(self.sorties)
        del sorties["M5"]
        with self.assertRaises(ValidationErreur):
            self.coordonner(sorties)

    def test_protections_sortie(self):
        resultat = self.coordonner()
        for champ in (
            "publication_autorisee",
            "fige_officiel",
            "fige_automatique",
            "validation_officielle",
            "archives_modifiees",
        ):
            self.assertIs(resultat[champ], False)

    def test_aucune_ecriture_directe(self):
        with patch(
            "builtins.open",
            side_effect=AssertionError(
                "Acces fichier interdit"
            ),
        ):
            resultat = self.coordonner()

        self.assertFalse(resultat["archives_modifiees"])

    def test_integration_reelle_des_moteurs(self):
        resultat = integration.executer_integration(
            copy.deepcopy(self.course)
        )
        self.assertTrue(resultat["coordination_complete"])
        self.assertEqual(resultat["nombre_moteurs"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
