#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X1000 V2.4 - Tests securises de coordination M1-M5.

Tests locaux avec donnees entierement fictives.
Aucune collecte PMU.
Aucun moteur execute.
Aucun FIGE ni publication.
Aucune modification des archives.
Aucune ecriture de donnees.
"""

from __future__ import annotations

import ast
import copy
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import coordination_x1000 as coordination
from validation_moteurs import MOTEURS, ValidationErreur
from test_validation_moteurs import course_test, sorties_test


RACINE = Path(__file__).resolve().parent


def creer_course():
    """Construire une course fictive avec un identifiant coherent."""
    course = course_test()

    depart = datetime.fromisoformat(course["depart"])
    date_locale = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).strftime("%Y-%m-%d")

    course["id"] = f"{date_locale}-R1-C1"

    return course


def creer_sorties():
    """Produire cinq classements fictifs independants."""
    return sorties_test()


class TestsCoordinationX1000(unittest.TestCase):

    def setUp(self):
        self.course = creer_course()
        self.sorties = creer_sorties()

    def coordonner_test(self, course=None, sorties=None):
        """
        Neutraliser uniquement la verification externe
        du noyau pour les donnees fictives.

        Conserver la validation reelle des partants,
        des moteurs et des classements.
        """
        if course is None:
            course = self.course

        if sorties is None:
            sorties = self.sorties

        with patch.object(
            coordination.noyau_commun,
            "verifier_course",
            return_value=(True, "TEST_SYNTHETIQUE"),
        ):
            return coordination.coordonner(course, sorties)

    def test_01_syntaxe_coordination(self):
        chemin = RACINE / "coordination_x1000.py"

        source = chemin.read_text(
            encoding="utf-8-sig"
        )

        ast.parse(source, filename=str(chemin))

    def test_02_cinq_moteurs_requis(self):
        self.assertEqual(
            set(MOTEURS),
            {"M1", "M2", "M3", "M4", "M5"},
        )

    def test_03_identifiant_course(self):
        identifiant = coordination.verifier_identifiant(
            self.course
        )

        self.assertRegex(
            identifiant,
            r"^\d{4}-\d{2}-\d{2}-R1-C1$",
        )

    def test_04_identifiant_invalide(self):
        for valeur in (None, "", "   ", True, 1.5):
            with self.subTest(valeur=valeur):
                course = copy.deepcopy(self.course)
                course["id"] = valeur

                with self.assertRaises(ValidationErreur):
                    coordination.verifier_identifiant(
                        course
                    )

    def test_05_sorties_valides(self):
        coordination.verifier_sorties(
            self.sorties
        )

    def test_06_moteur_manquant(self):
        sorties = copy.deepcopy(self.sorties)
        del sorties["M5"]

        with self.assertRaises(ValidationErreur):
            coordination.verifier_sorties(sorties)

    def test_07_moteur_supplementaire(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M6"] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValidationErreur):
            coordination.verifier_sorties(sorties)

    def test_08_notes_valides(self):
        for valeur in (None, 0, 50, 100, 82.5):
            with self.subTest(valeur=valeur):
                coordination.verifier_note(
                    valeur,
                    "test",
                )

    def test_09_notes_invalides(self):
        valeurs = (
            -1,
            101,
            True,
            "80",
            float("nan"),
            float("inf"),
        )

        for valeur in valeurs:
            with self.subTest(valeur=valeur):
                with self.assertRaises(
                    ValidationErreur
                ):
                    coordination.verifier_note(
                        valeur,
                        "test",
                    )

    def test_10_coordination_complete(self):
        resultat = self.coordonner_test()

        self.assertEqual(
            resultat["statut"],
            coordination.STATUT_COMPLET,
        )

        self.assertTrue(
            resultat["coordination_complete"]
        )

        self.assertEqual(
            resultat["nombre_moteurs"],
            5,
        )

        self.assertEqual(
            set(resultat["moteurs_complets"]),
            set(MOTEURS),
        )

        self.assertEqual(
            resultat["moteurs_incomplets"],
            [],
        )

    def test_11_predictions_independantes(self):
        resultat = self.coordonner_test()

        predictions = resultat[
            "predictions_independantes"
        ]

        self.assertEqual(
            predictions,
            self.sorties,
        )

        self.assertEqual(
            len({
                tuple(v)
                for v in predictions.values()
            }),
            5,
        )

    def test_12_empreinte_sha256(self):
        resultat = self.coordonner_test()

        empreinte = resultat[
            "empreinte_sha256"
        ]

        self.assertTrue(
            re.fullmatch(
                r"[0-9a-f]{64}",
                empreinte,
            )
        )

    def test_13_empreinte_stable(self):
        premier = self.coordonner_test()
        second = self.coordonner_test()

        self.assertEqual(
            premier["empreinte_sha256"],
            second["empreinte_sha256"],
        )

    def test_14_empreinte_sensible(self):
        premier = self.coordonner_test()

        sorties = copy.deepcopy(self.sorties)
        sorties["M1"] = list(
            reversed(sorties["M1"])
        )

        second = self.coordonner_test(
            sorties=sorties
        )

        self.assertNotEqual(
            premier["empreinte_sha256"],
            second["empreinte_sha256"],
        )

    def test_15_aucune_mutation(self):
        course_avant = copy.deepcopy(
            self.course
        )

        sorties_avant = copy.deepcopy(
            self.sorties
        )

        self.coordonner_test()

        self.assertEqual(
            self.course,
            course_avant,
        )

        self.assertEqual(
            self.sorties,
            sorties_avant,
        )

    def test_16_aucune_publication(self):
        resultat = self.coordonner_test()

        protections = (
            "publication_autorisee",
            "fige_officiel",
            "fige_automatique",
            "validation_officielle",
            "archives_modifiees",
        )

        for cle in protections:
            with self.subTest(cle=cle):
                self.assertIs(
                    resultat[cle],
                    False,
                )

    def test_17_non_partant_refuse(self):
        sorties = copy.deepcopy(self.sorties)

        sorties["M1"] = [1, 2, 3, 4, 7]

        with self.assertRaises(
            ValidationErreur
        ):
            self.coordonner_test(
                sorties=sorties
            )

    def test_18_doublon_refuse(self):
        sorties = copy.deepcopy(self.sorties)

        sorties["M2"] = [1, 1, 3, 4, 5]

        with self.assertRaises(
            ValidationErreur
        ):
            self.coordonner_test(
                sorties=sorties
            )

    def test_19_alias_compatibilite(self):
        with patch.object(
            coordination,
            "coordonner",
            return_value={"test": "OK"},
        ) as fonction:
            resultat = (
                coordination.coordonner_predictions(
                    self.course,
                    self.sorties,
                )
            )

        self.assertEqual(
            resultat,
            {"test": "OK"},
        )

        fonction.assert_called_once_with(
            self.course,
            self.sorties,
        )

    def test_20_format_historique(self):
        resultat = self.coordonner_test()

        analyses = resultat[
            "analyses_independantes"
        ]

        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                self.assertEqual(
                    analyses[moteur]["format"],
                    "LISTE_HISTORIQUE",
                )

                self.assertEqual(
                    analyses[moteur]["classement"],
                    self.sorties[moteur],
                )


def main():
    print(
        "X1000 V2.4 - Tests de coordination M1-M5",
        flush=True,
    )

    print(
        "Donnees fictives - Aucun FIGE - "
        "Aucune publication",
        flush=True,
    )

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestsCoordinationX1000
    )

    resultat = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
    ).run(suite)

    return 0 if resultat.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
