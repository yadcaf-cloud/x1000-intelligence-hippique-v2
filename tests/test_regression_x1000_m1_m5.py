#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests de regression X1000 M1-M5, sans ecriture metier."""

import copy
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from moteurs import noyau_commun
from validation_moteurs import (
    ValidationErreur,
    valider_course,
    valider_prediction,
    valider_predictions_moteurs,
)

NOMS = ("M1", "M2", "M3", "M4", "M5")


def creer_course():
    depart = datetime.now(timezone.utc) + timedelta(days=2)
    date_fr = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).date().isoformat()

    chevaux = []
    for numero in range(1, 8):
        cheval = {
            "numero": numero,
            "nom": f"TEST_{numero}",
            "non_partant": numero == 7,
        }

        for nom in NOMS:
            module = importlib.import_module(
                f"moteurs.{nom.lower()}"
            )
            cheval[module.CHAMP] = {
                critere: 90 - numero * 5
                for critere in module.POIDS
            }

        chevaux.append(cheval)

    return {
        "id": f"{date_fr}-R1-C1",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart.isoformat(),
        "partants": chevaux,
        "nombre_partants": 6,
        "non_partants": [7],
    }


class TestRegressionX1000(unittest.TestCase):

    def setUp(self):
        self.course = creer_course()

    def analyser(self, nom, course=None):
        module = importlib.import_module(
            f"moteurs.{nom.lower()}"
        )
        return noyau_commun.analyser_course(
            copy.deepcopy(
                self.course if course is None else course
            ),
            nom,
            module.POIDS,
            module.CHAMP,
            module.COUVERTURE_MIN,
        )

    def test_01_cinq_modules_presents(self):
        for nom in NOMS:
            with self.subTest(moteur=nom):
                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )
                self.assertEqual(module.MOTEUR, nom)
                self.assertTrue(module.POIDS)
                self.assertTrue(module.CHAMP)

    def test_02_course_valide(self):
        self.assertEqual(
            valider_course(self.course),
            {1, 2, 3, 4, 5, 6},
        )

    def test_03_cinq_analyses_completes(self):
        for nom in NOMS:
            with self.subTest(moteur=nom):
                resultat = self.analyser(nom)
                self.assertEqual(
                    resultat["statut"],
                    "ANALYSE_DISPONIBLE",
                )
                self.assertEqual(
                    len(resultat["classement"]), 5
                )
                self.assertFalse(resultat["fige"])
                self.assertFalse(resultat["publication"])
                noyau_commun.verifier_sortie_analyse(
                    resultat, self.course
                )

    def test_04_non_partant_exclu(self):
        for nom in NOMS:
            resultat = self.analyser(nom)
            numeros = [
                p["numero"]
                for p in resultat["classement"]
            ]
            self.assertNotIn(7, numeros)

    def test_05_donnees_insuffisantes(self):
        course = copy.deepcopy(self.course)
        module = importlib.import_module("moteurs.m1")
        course["partants"][0].pop(module.CHAMP)

        resultat = self.analyser("M1", course)
        self.assertEqual(
            resultat["statut"],
            "ANALYSE_DISPONIBLE",
        )
        self.assertEqual(
            len(resultat["classement"]), 5
        )

        for cheval in course["partants"][:3]:
            cheval.pop(module.CHAMP, None)

        resultat = self.analyser("M1", course)
        self.assertEqual(
            resultat["statut"],
            "DONNEES_INSUFFISANTES",
        )
        self.assertEqual(resultat["classement"], [])

    def test_06_rejet_doublons(self):
        actifs = valider_course(self.course)
        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M1", [1, 1, 2, 3, 4], actifs
            )

    def test_07_rejet_non_partant(self):
        actifs = valider_course(self.course)
        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M2", [1, 2, 3, 4, 7], actifs
            )

    def test_08_rejet_course_non_verifiee(self):
        course = copy.deepcopy(self.course)
        course["localisation_france_verifiee"] = False

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_09_rejet_depart_passe(self):
        course = copy.deepcopy(self.course)
        course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(hours=1)
        ).isoformat()

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_10_independance_des_donnees(self):
        course = copy.deepcopy(self.course)
        original = copy.deepcopy(course)

        for nom in NOMS:
            self.analyser(nom, course)

        self.assertEqual(course, original)

    def test_11_predictions_independantes(self):
        actifs = valider_course(self.course)
        predictions = {
            "M1": [1, 2, 3, 4, 5],
            "M2": [2, 3, 4, 5, 6],
            "M3": [3, 4, 5, 6, 1],
            "M4": [4, 5, 6, 1, 2],
            "M5": [5, 6, 1, 2, 3],
        }

        copie = copy.deepcopy(predictions)
        resultats = valider_predictions_moteurs(
            predictions, actifs
        )

        self.assertEqual(resultats, predictions)
        resultats["M1"][0] = 6
        self.assertEqual(predictions, copie)

    def test_12_rejet_fige_publication(self):
        resultat = self.analyser("M1")

        for champ in ("fige", "publication"):
            avec_interdit = copy.deepcopy(resultat)
            avec_interdit[champ] = True

            with self.assertRaises(ValueError):
                noyau_commun.verifier_sortie_analyse(
                    avec_interdit, self.course
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
