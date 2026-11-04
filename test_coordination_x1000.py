#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - TESTS D'INTEGRATION M1-M5

Tests techniques exclusivement.

- Aucun acces PMU
- Aucune prediction reelle
- Aucun FIGE
- Aucune publication
- Aucune ecriture dans les archives

Execution :
    python -m unittest -v test_coordination_x1000.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import unittest

from datetime import datetime, timedelta, timezone

from coordination_x1000 import coordonner

from validation_moteurs import ValidationErreur

from moteurs import noyau_commun


MOTEURS = tuple(
    f"M{i}" for i in range(1, 6)
)


def fabriquer_course():
    """
    Course fictive exclusivement destinee
    aux tests logiciels.
    """

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=1)
    ).isoformat()

    return {
        "id": "TEST-2026-R1-C1",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart,
        "nombre_partants": 6,
        "non_partants": [],
        "partants": [
            {
                "numero": numero,
                "nom": f"Cheval test {numero}",
                "non_partant": False,
            }
            for numero in range(1, 7)
        ],
    }


def fabriquer_position(numero, rang):
    return {
        "position_predite": rang,
        "numero": numero,
        "nom": f"Cheval test {numero}",
        "score": float(90 - rang * 5),
        "couverture": 1.0,
        "risques": [],
    }


def fabriquer_resultat(
    moteur,
    course,
    numeros=None,
    statut="ANALYSE_DISPONIBLE",
):
    if numeros is None:
        numeros = [1, 2, 3, 4, 5]

    positions = [
        fabriquer_position(numero, rang)
        for rang, numero in enumerate(
            numeros,
            start=1,
        )
    ]

    complet = statut == "ANALYSE_DISPONIBLE"

    return {
        "moteur": moteur,
        "version": "2.4",
        "course_id": course["id"],
        "analyse_a": datetime.now(
            timezone.utc
        ).isoformat(),
        "statut": statut,
        "raison": "Donnees fictives de test",
        "classement": positions if complet else [],
        "classement_partiel": (
            [] if complet else positions
        ),
        "fige": False,
        "publication": False,
    }


def fabriquer_sorties(course):
    return {
        moteur: fabriquer_resultat(
            moteur,
            course,
        )
        for moteur in MOTEURS
    }


class TestsCoordinationX1000(unittest.TestCase):

    def setUp(self):
        self.course = fabriquer_course()
        self.sorties = fabriquer_sorties(
            self.course
        )

    def test_01_noyau_version(self):
        self.assertEqual(
            noyau_commun.VERSION,
            "2.4",
        )

    def test_02_cinq_moteurs_importables(self):
        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                module = importlib.import_module(
                    f"moteurs.{moteur.lower()}"
                )

                self.assertEqual(
                    module.MOTEUR,
                    moteur,
                )

                self.assertTrue(
                    callable(module.analyser_course)
                )

    def test_03_course_valide(self):
        valide, raison = (
            noyau_commun.verifier_course(
                self.course
            )
        )

        self.assertTrue(valide, raison)

    def test_04_coordination_complete(self):
        resultat = coordonner(
            self.course,
            self.sorties,
        )

        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE",
        )

        self.assertTrue(
            resultat["coordination_complete"]
        )

        self.assertEqual(
            len(resultat["predictions_independantes"]),
            5,
        )

        self.assertEqual(
            resultat["moteurs_incomplets"],
            [],
        )

    def test_05_classements_independants(self):
        self.sorties["M2"]["classement"] = [
            fabriquer_position(n, rang)
            for rang, n in enumerate(
                [5, 4, 3, 2, 1],
                start=1,
            )
        ]

        resultat = coordonner(
            self.course,
            self.sorties,
        )

        self.assertEqual(
            resultat["predictions_independantes"]["M1"],
            [1, 2, 3, 4, 5],
        )

        self.assertEqual(
            resultat["predictions_independantes"]["M2"],
            [5, 4, 3, 2, 1],
        )

    def test_06_coordination_partielle(self):
        self.sorties["M3"] = fabriquer_resultat(
            "M3",
            self.course,
            numeros=[1, 2, 3],
            statut="DONNEES_INSUFFISANTES",
        )

        resultat = coordonner(
            self.course,
            self.sorties,
        )

        self.assertEqual(
            resultat["statut"],
            "COORDINATION_INCOMPLETE_NON_PUBLIE",
        )

        self.assertFalse(
            resultat["coordination_complete"]
        )

        self.assertIn(
            "M3",
            resultat["moteurs_incomplets"],
        )

        self.assertEqual(
            resultat["predictions_partielles"]["M3"],
            [1, 2, 3],
        )

        self.assertEqual(
            resultat["predictions_independantes"],
            {},
        )

    def test_07_doublon_refuse(self):
        self.sorties["M1"]["classement"][1][
            "numero"
        ] = 1

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_08_non_partant_refuse(self):
        self.course["partants"][0][
            "non_partant"
        ] = True

        self.course["non_partants"] = [1]
        self.course["nombre_partants"] = 5

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_09_publication_refusee(self):
        self.sorties["M4"][
            "publication"
        ] = True

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_10_fige_refuse(self):
        self.sorties["M5"]["fige"] = True

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_11_moteur_manquant_refuse(self):
        del self.sorties["M5"]

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_12_course_hors_france_refusee(self):
        self.course[
            "localisation_france_verifiee"
        ] = False

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_13_course_passee_refusee(self):
        self.course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(hours=1)
        ).isoformat()

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_14_aucune_modification_entrees(self):
        course_initiale = copy.deepcopy(
            self.course
        )

        sorties_initiales = copy.deepcopy(
            self.sorties
        )

        coordonner(
            self.course,
            self.sorties,
        )

        self.assertEqual(
            self.course,
            course_initiale,
        )

        self.assertEqual(
            self.sorties,
            sorties_initiales,
        )

    def test_15_empreinte_sha256(self):
        resultat = coordonner(
            self.course,
            self.sorties,
        )

        empreinte = resultat[
            "empreinte_sha256"
        ]

        self.assertEqual(
            len(empreinte),
            64,
        )

        self.assertTrue(
            all(
                caractere in "0123456789abcdef"
                for caractere in empreinte
            )
        )

        resultat2 = coordonner(
            self.course,
            self.sorties,
        )

        self.assertEqual(
            empreinte,
            resultat2["empreinte_sha256"],
        )

    def test_16_sorties_sans_donnees_sportives(self):
        """
        Les vrais moteurs ne doivent pas inventer
        de classement en l'absence d'indicateurs.
        """

        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                module = importlib.import_module(
                    f"moteurs.{moteur.lower()}"
                )

                resultat = module.analyser_course(
                    copy.deepcopy(self.course)
                )

                noyau_commun.verifier_sortie_analyse(
                    self.course,
                    resultat,
                )

                self.assertEqual(
                    resultat["statut"],
                    "DONNEES_INSUFFISANTES",
                )

                self.assertEqual(
                    resultat["classement"],
                    [],
                )

                self.assertEqual(
                    resultat["classement_partiel"],
                    [],
                )

                self.assertIs(
                    resultat["fige"],
                    False,
                )

                self.assertIs(
                    resultat["publication"],
                    False,
                )

    def test_17_format_historique(self):
        sorties = {
            moteur: [1, 2, 3, 4, 5]
            for moteur in MOTEURS
        }

        resultat = coordonner(
            self.course,
            sorties,
        )

        self.assertTrue(
            resultat["coordination_complete"]
        )

    def test_18_ordre_invalide_refuse(self):
        self.sorties["M2"]["classement"][0][
            "position_predite"
        ] = 3

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_19_nom_incoherent_refuse(self):
        self.sorties["M1"]["classement"][0][
            "nom"
        ] = "Cheval inconnu"

        with self.assertRaises(
            ValidationErreur
        ):
            coordonner(
                self.course,
                self.sorties,
            )

    def test_20_protections_finales(self):
        resultat = coordonner(
            self.course,
            self.sorties,
        )

        for cle in (
            "publication_autorisee",
            "fige_officiel",
            "fige_automatique",
            "validation_officielle",
            "archives_modifiees",
        ):
            self.assertIs(
                resultat[cle],
                False,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
