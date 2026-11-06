#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 Intelligence Hippique V2
Audit de bout en bout M1-M5.

Tests locaux et fictifs uniquement.
Aucune collecte PMU.
Aucun FIGE automatique.
Aucune publication.
Aucune modification des archives.
"""

import copy
import unittest
from unittest.mock import patch

import coordination_x1000 as central
import integration_x1000 as integration
from validation_moteurs import ValidationErreur


MOTEURS = ("M1", "M2", "M3", "M4", "M5")

PROTECTIONS = (
    "publication_autorisee",
    "fige_officiel",
    "fige_automatique",
    "validation_officielle",
    "archives_modifiees",
)


class TestBoutEnBoutX1000(unittest.TestCase):

    def setUp(self):
        self.course = integration.creer_course_test()

    def test_cinq_moteurs_charges(self):
        moteurs = integration.charger_moteurs()
        self.assertEqual(set(moteurs), set(MOTEURS))

        for nom, module in moteurs.items():
            self.assertEqual(module.MOTEUR, nom)
            self.assertTrue(
                callable(module.analyser_course)
            )

    def test_execution_complete(self):
        original = copy.deepcopy(self.course)

        resultat = integration.executer_integration(
            self.course
        )

        self.assertEqual(self.course, original)
        self.assertTrue(
            resultat["coordination_complete"]
        )
        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(MOTEURS),
        )

        for nom, classement in resultat[
            "predictions_independantes"
        ].items():
            with self.subTest(moteur=nom):
                self.assertEqual(len(classement), 5)
                self.assertEqual(len(set(classement)), 5)
                self.assertNotIn(7, classement)

    def test_comparaison_des_coordinateurs(self):
        modules = integration.charger_moteurs()

        sorties = {
            nom: module.analyser_course(
                copy.deepcopy(self.course)
            )
            for nom, module in modules.items()
        }

        a = integration.coordonner(
            copy.deepcopy(self.course),
            copy.deepcopy(sorties),
        )

        b = central.coordonner(
            copy.deepcopy(self.course),
            copy.deepcopy(sorties),
        )

        for champ in (
            "coordination_complete",
            "nombre_moteurs",
            "moteurs_complets",
            "moteurs_incomplets",
            "predictions_independantes",
            "predictions_partielles",
        ):
            with self.subTest(champ=champ):
                self.assertEqual(a[champ], b[champ])

    def test_reproductibilite(self):
        a = integration.executer_integration(
            copy.deepcopy(self.course)
        )
        b = integration.executer_integration(
            copy.deepcopy(self.course)
        )

        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"],
        )

    def test_protections(self):
        resultat = integration.executer_integration(
            copy.deepcopy(self.course)
        )

        for champ in PROTECTIONS:
            with self.subTest(champ=champ):
                self.assertIs(resultat[champ], False)

    def test_refus_fige_et_publication(self):
        modules = integration.charger_moteurs()

        sorties = {
            nom: module.analyser_course(
                copy.deepcopy(self.course)
            )
            for nom, module in modules.items()
        }

        for nom in MOTEURS:
            for champ in ("fige", "publication"):
                with self.subTest(
                    moteur=nom, champ=champ
                ):
                    invalides = copy.deepcopy(sorties)
                    invalides[nom][champ] = True

                    with self.assertRaises(
                        ValidationErreur
                    ):
                        integration.coordonner(
                            copy.deepcopy(self.course),
                            invalides,
                        )

    def test_aucune_ecriture_coordination(self):
        modules = integration.charger_moteurs()

        sorties = {
            nom: module.analyser_course(
                copy.deepcopy(self.course)
            )
            for nom, module in modules.items()
        }

        with patch(
            "builtins.open",
            side_effect=AssertionError(
                "Acces fichier interdit"
            ),
        ):
            resultat = central.coordonner(
                copy.deepcopy(self.course),
                copy.deepcopy(sorties),
            )

        self.assertFalse(
            resultat["archives_modifiees"]
        )

    def test_course_passee_refusee(self):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        course = copy.deepcopy(self.course)
        depart = datetime.now(
            ZoneInfo("Europe/Paris")
        ) - timedelta(days=1)

        course["depart"] = depart.isoformat()
        course["id"] = (
            depart.strftime("%Y-%m-%d") + "-R1-C1"
        )

        with self.assertRaises(
            (ValidationErreur, ValueError)
        ):
            integration.executer_integration(course)

    def test_api_lecture_seule(self):
        try:
            from fastapi.testclient import TestClient
            from api import app
        except ImportError as exc:
            self.fail(
                "Dependance API manquante : " + str(exc)
            )

        with TestClient(app) as client:
            routes = (
                "/api/status",
                "/api/courses",
                "/api/selections",
                "/api/figes",
                "/api/audits",
                "/api/diagnostic",
            )

            for route in routes:
                with self.subTest(route=route):
                    reponse = client.get(route)
                    self.assertEqual(
                        reponse.status_code, 200
                    )

            reponse = client.post("/api/figes")
            self.assertEqual(reponse.status_code, 405)

            reponse = client.put("/api/audits")
            self.assertEqual(reponse.status_code, 405)

            reponse = client.delete("/api/courses")
            self.assertEqual(reponse.status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
