#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Audit integral M1-M5 et coordination centrale.

Tests locaux sur course fictive.
Aucune collecte PMU.
Aucun FIGE automatique.
Aucune publication.
Aucune ecriture dans les archives.
"""

import copy
import importlib
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


class TestAuditIntegralX1000(unittest.TestCase):

    def setUp(self):
        self.course = integration.creer_course_test()
        self.reference = copy.deepcopy(self.course)

    def sorties_valides(self):
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
                f"Protection non respectee : {cle}"
            )

    def test_01_cinq_moteurs_charges(self):
        moteurs = integration.charger_moteurs()
        self.assertEqual(set(moteurs), set(MOTEURS))

    def test_02_identites_et_versions(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )
                self.assertEqual(module.MOTEUR, nom)
                self.assertEqual(module.VERSION, "2.4")
                self.assertTrue(
                    callable(module.analyser_course)
                )
                module.verifier_noyau()

    def test_03_autotests_individuels(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )
                self.assertTrue(module.self_test())

    def test_04_analyses_independantes(self):
        sorties = self.sorties_valides()

        self.assertEqual(set(sorties), set(MOTEURS))

        for nom, resultat in sorties.items():
            with self.subTest(moteur=nom):
                self.assertEqual(
                    resultat["moteur"], nom
                )
                self.assertIs(resultat["fige"], False)
                self.assertIs(
                    resultat["publication"], False
                )
                integration.verifier_resultat(
                    nom, resultat, self.course
                )

        self.assertEqual(self.course, self.reference)

    def test_05_classements_coherents(self):
        sorties = self.sorties_valides()

        for nom, resultat in sorties.items():
            with self.subTest(moteur=nom):
                statut = resultat["statut"]
                classement = resultat["classement"]

                if statut == "ANALYSE_DISPONIBLE":
                    self.assertEqual(
                        len(classement), 5
                    )

                    numeros = [
                        cheval["numero"]
                        for cheval in classement
                    ]

                    self.assertEqual(
                        len(numeros),
                        len(set(numeros))
                    )
                else:
                    self.assertEqual(classement, [])

    def test_06_coordination_integration(self):
        sorties = self.sorties_valides()
        resultat = integration.coordonner(
            self.course, sorties
        )

        self.assertEqual(
            resultat["nombre_moteurs"], 5
        )
        self.assertEqual(
            set(resultat["analyses_independantes"]),
            set(MOTEURS)
        )
        self.verifier_protections(resultat)
        self.assertEqual(self.course, self.reference)

    def test_07_coordination_centrale(self):
        sorties = self.sorties_valides()
        resultat = central.coordonner(
            self.course, sorties
        )

        self.assertEqual(
            resultat["nombre_moteurs"], 5
        )
        self.assertEqual(
            set(resultat["analyses_independantes"]),
            set(MOTEURS)
        )
        self.verifier_protections(resultat)

    def test_08_execution_complete(self):
        resultat = integration.executer_integration(
            copy.deepcopy(self.course)
        )

        self.assertEqual(
            resultat["nombre_moteurs"], 5
        )
        self.verifier_protections(resultat)
        self.assertEqual(self.course, self.reference)

    def test_09_moteur_manquant_refuse(self):
        sorties = self.sorties_valides()
        del sorties["M5"]

        with self.assertRaises(ValidationErreur):
            integration.coordonner(
                self.course, sorties
            )

    def test_10_identite_falsifiee_refusee(self):
        sorties = self.sorties_valides()
        sorties["M1"]["moteur"] = "M2"

        with self.assertRaises(ValidationErreur):
            integration.coordonner(
                self.course, sorties
            )

    def test_11_fige_interdit(self):
        sorties = self.sorties_valides()
        sorties["M1"]["fige"] = True

        with self.assertRaises(ValidationErreur):
            integration.coordonner(
                self.course, sorties
            )

    def test_12_publication_interdite(self):
        sorties = self.sorties_valides()
        sorties["M2"]["publication"] = True

        with self.assertRaises(ValidationErreur):
            integration.coordonner(
                self.course, sorties
            )

    def test_13_resultats_deterministes(self):
        moteurs = integration.charger_moteurs()

        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                premier = moteurs[nom].analyser_course(
                    copy.deepcopy(self.course)
                )
                second = moteurs[nom].analyser_course(
                    copy.deepcopy(self.course)
                )

                self.assertEqual(
                    premier["statut"],
                    second["statut"]
                )
                self.assertEqual(
                    premier["classement"],
                    second["classement"]
                )
                self.assertEqual(
                    premier["classement_partiel"],
                    second["classement_partiel"]
                )

    def test_14_erreur_moteur_interrompt(self):
        moteurs = integration.charger_moteurs()

        def erreur_simulee(course):
            raise RuntimeError("Panne fictive M3")

        moteurs = dict(moteurs)
        moteur_m3 = copy.copy(moteurs["M3"])
        moteur_m3.analyser_course = erreur_simulee
        moteurs["M3"] = moteur_m3

        with patch.object(
            integration,
            "charger_moteurs",
            return_value=moteurs
        ):
            with self.assertRaises(RuntimeError):
                integration.executer_integration(
                    copy.deepcopy(self.course)
                )

    def test_15_aucune_mutation_entree(self):
        integration.executer_integration(
            copy.deepcopy(self.course)
        )
        self.assertEqual(
            self.course,
            self.reference
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
