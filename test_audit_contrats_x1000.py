#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Diagnostic technique M1 à M5.

- Données exclusivement synthétiques
- Aucune collecte PMU
- Aucun FIGÉ automatique
- Aucune publication automatique
- Aucune modification des archives
- Aucune écriture de données métier
"""

import copy
import importlib
import unittest

from datetime import datetime, timedelta, timezone

from moteurs import noyau_commun


MOTEURS = ("M1", "M2", "M3", "M4", "M5")


def course_synthetique():
    """Construit une course fictive pour les tests."""

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
    ).replace(microsecond=0).isoformat()

    partants = []

    for numero in range(1, 8):

        cheval = {
            "numero": numero,
            "nom": f"TEST_{numero}",
            "non_partant": numero == 7,
        }

        for nom in MOTEURS:

            module = importlib.import_module(
                f"moteurs.{nom.lower()}"
            )

            cheval[module.CHAMP] = {
                critere: 50 + numero
                for critere in module.POIDS
            }

        partants.append(cheval)

    return {
        "id": "TEST-SYNTHETIQUE-NON-PMU",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart,
        "partants": partants,
        "nombre_partants": 6,
        "non_partants": [7],
    }


class TestContratsX1000(unittest.TestCase):

    def test_cinq_moteurs_independants(self):
        """Vérifie les sorties des cinq moteurs."""

        course = course_synthetique()
        original = copy.deepcopy(course)

        for nom in MOTEURS:

            with self.subTest(moteur=nom):

                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )

                self.assertEqual(
                    module.MOTEUR, nom
                )

                module.verifier_noyau()

                sortie = module.analyser_course(
                    copy.deepcopy(course)
                )

                noyau_commun.verifier_sortie_analyse(
                    sortie, course
                )

                self.assertEqual(
                    sortie["statut"],
                    "ANALYSE_DISPONIBLE"
                )

                self.assertEqual(
                    len(sortie["classement"]), 5
                )

                self.assertFalse(sortie["fige"])
                self.assertFalse(sortie["publication"])

                numeros = [
                    cheval["numero"]
                    for cheval in sortie["classement"]
                ]

                self.assertEqual(
                    len(numeros),
                    len(set(numeros))
                )

                self.assertNotIn(7, numeros)

        self.assertEqual(course, original)

    def test_course_passee_refusee(self):
        """Une course terminée ne doit pas être analysable."""

        course = course_synthetique()

        course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(days=1)
        ).isoformat()

        valide, _ = noyau_commun.verifier_course(
            course
        )

        self.assertFalse(valide)

    def test_non_partant_incoherent_refuse(self):
        """Détecte une liste de non-partants incohérente."""

        course = course_synthetique()
        course["non_partants"] = []

        valide, _ = noyau_commun.verifier_course(
            course
        )

        self.assertFalse(valide)

    def test_donnees_absentes_sans_pronostic(self):
        """Aucune prédiction complète sans indicateurs."""

        course = course_synthetique()

        for cheval in course["partants"]:

            for nom in MOTEURS:

                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )

                cheval.pop(module.CHAMP, None)

        for nom in MOTEURS:

            with self.subTest(moteur=nom):

                module = importlib.import_module(
                    f"moteurs.{nom.lower()}"
                )

                sortie = module.analyser_course(
                    copy.deepcopy(course)
                )

                self.assertEqual(
                    sortie["classement"], []
                )

                self.assertFalse(sortie["fige"])
                self.assertFalse(sortie["publication"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
