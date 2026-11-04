#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 PHOENIX — TESTS V2.4

Tests synthétiques, sans données PMU réelles.
Aucun FIGÉ ni aucune archive modifiés.
Aucune publication.
"""

import unittest
import copy

from datetime import (
    datetime,
    timezone,
    timedelta,
)

from importlib import import_module

from moteurs import noyau_commun as noyau


MOTEURS = [
    import_module(f"moteurs.m{i}")
    for i in range(1, 6)
]


def course_test():

    return {
        "id": "2026-12-31-R1-C1",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": (
            datetime.now(timezone.utc)
            + timedelta(days=30)
        ).isoformat(timespec="seconds"),
        "partants": [
            {
                "numero": i,
                "nom": f"Cheval {i}",
                "non_partant": False,
            }
            for i in range(1, 6)
        ],
    }


class TestX1000(unittest.TestCase):

    def test_versions(self):

        self.assertEqual(
            noyau.VERSION, "2.4"
        )

        for moteur in MOTEURS:

            self.assertEqual(
                moteur.VERSION,
                noyau.VERSION
            )

            self.assertTrue(
                moteur.self_test()
            )

    def test_notes_invalides(self):

        valeurs = [
            True,
            False,
            float("nan"),
            float("inf"),
            -1,
            101,
            "50",
        ]

        for valeur in valeurs:

            self.assertIsNone(
                noyau.note_valide(valeur)
            )

    def test_identifiant_invalide(self):

        course = course_test()
        course["id"] = True

        valide, raison = noyau.verifier_course(
            course
        )

        self.assertFalse(valide)

    def test_classement_et_non_partant(self):

        for moteur in MOTEURS:

            course = course_test()

            course["partants"].append({
                "numero": 6,
                "nom": "Non-partant",
                "non_partant": True,
            })

            course["non_partants"] = [6]

            for cheval in course["partants"]:

                cheval[moteur.CHAMP] = {
                    critere: float(
                        100 - cheval["numero"] * 8
                    )
                    for critere in moteur.POIDS
                }

            reference = copy.deepcopy(course)

            resultat = moteur.analyser_course(
                course
            )

            self.assertEqual(
                course, reference
            )

            self.assertEqual(
                resultat["statut"],
                "ANALYSE_DISPONIBLE"
            )

            self.assertEqual(
                len(resultat["classement"]), 5
            )

            numeros = [
                cheval["numero"]
                for cheval in resultat["classement"]
            ]

            self.assertNotIn(6, numeros)

            self.assertIs(
                resultat["fige"], False
            )

            self.assertIs(
                resultat["publication"], False
            )

            classement = resultat["classement"]

            classement[0], classement[1] = (
                classement[1], classement[0]
            )

            for position, cheval in enumerate(
                classement, start=1
            ):
                cheval["position_predite"] = position

            with self.assertRaises(RuntimeError):
                moteur.verifier_resultat(resultat)

    def test_donnees_insuffisantes(self):

        for moteur in MOTEURS:

            resultat = moteur.analyser_course(
                course_test()
            )

            self.assertEqual(
                resultat["statut"],
                "DONNEES_INSUFFISANTES"
            )

            self.assertEqual(
                resultat["classement"], []
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
