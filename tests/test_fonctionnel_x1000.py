#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
Tests fonctionnels renforces M1 a M5.

12 tests de validation.

Donnees entierement synthetiques.
Aucune collecte PMU.
Aucun FIGE automatique.
Aucune publication automatique.
Aucune modification des archives.
"""

import copy
import importlib
import unittest

from datetime import datetime, timedelta, timezone
from moteurs import noyau_commun


NOMS = ("m1", "m2", "m3", "m4", "m5")

MOTEURS = {
    nom: importlib.import_module(f"moteurs.{nom}")
    for nom in NOMS
}


def creer_course():
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

        for nom, moteur in MOTEURS.items():
            cheval[moteur.CHAMP] = {
                critere: 90 - numero * 5
                for critere in moteur.POIDS
            }

        partants.append(cheval)

    return {
        "id": "TEST-FONCTIONNEL-X1000",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart,
        "partants": partants,
        "nombre_partants": 6,
        "non_partants": [7],
    }


class TestFonctionnelX1000(unittest.TestCase):

    def analyser(self, nom, course):
        moteur = MOTEURS[nom]

        resultat = moteur.analyser_course(
            copy.deepcopy(course)
        )

        noyau_commun.verifier_sortie_analyse(
            resultat, course
        )

        return resultat

    def test_01_identite_moteurs(self):
        for nom, moteur in MOTEURS.items():
            with self.subTest(moteur=nom):
                self.assertEqual(
                    moteur.MOTEUR,
                    nom.upper()
                )

                self.assertEqual(
                    moteur.VERSION,
                    "2.4"
                )

                moteur.verifier_noyau()

    def test_02_cinq_positions(self):
        course = creer_course()

        for nom in NOMS:
            with self.subTest(moteur=nom):
                resultat = self.analyser(
                    nom, course
                )

                self.assertEqual(
                    resultat["statut"],
                    "ANALYSE_DISPONIBLE"
                )

                self.assertEqual(
                    len(resultat["classement"]),
                    5
                )

                numeros = [
                    cheval["numero"]
                    for cheval in resultat["classement"]
                ]

                self.assertEqual(
                    len(numeros),
                    len(set(numeros))
                )

                self.assertNotIn(7, numeros)

    def test_03_lecture_seule(self):
        course = creer_course()
        original = copy.deepcopy(course)

        for nom in NOMS:
            self.analyser(nom, course)

        self.assertEqual(
            course,
            original
        )

    def test_04_aucun_fige_publication(self):
        course = creer_course()

        for nom in NOMS:
            with self.subTest(moteur=nom):
                resultat = self.analyser(
                    nom, course
                )

                self.assertIs(
                    resultat["fige"],
                    False
                )

                self.assertIs(
                    resultat["publication"],
                    False
                )

    def test_05_course_passee(self):
        course = creer_course()

        course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(days=1)
        ).isoformat()

        for nom in NOMS:
            with self.subTest(moteur=nom):
                moteur = MOTEURS[nom]

                resultat = moteur.analyser_course(
                    copy.deepcopy(course)
                )

                self.assertEqual(
                    resultat["statut"],
                    "NON_ANALYSABLE"
                )

                self.assertEqual(
                    resultat["classement"],
                    []
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "Depart deja passe"
                ):
                    noyau_commun.verifier_sortie_analyse(
                        resultat,
                        course
                    )

    def test_06_non_partants(self):
        course = creer_course()

        course["non_partants"] = []

        for nom in NOMS:
            with self.subTest(moteur=nom):
                moteur = MOTEURS[nom]

                resultat = moteur.analyser_course(
                    copy.deepcopy(course)
                )

                self.assertEqual(
                    resultat["statut"],
                    "NON_ANALYSABLE"
                )

                self.assertEqual(
                    resultat["classement"],
                    []
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "Liste des non-partants incoherente"
                ):
                    noyau_commun.verifier_sortie_analyse(
                        resultat,
                        course
                    )

    def test_07_donnees_absentes(self):
        course = creer_course()

        for cheval in course["partants"]:
            for moteur in MOTEURS.values():
                cheval.pop(
                    moteur.CHAMP,
                    None
                )

        for nom in NOMS:
            with self.subTest(moteur=nom):
                resultat = self.analyser(
                    nom, course
                )

                self.assertEqual(
                    resultat["classement"],
                    []
                )

                self.assertNotEqual(
                    resultat["statut"],
                    "ANALYSE_DISPONIBLE"
                )

    def test_08_scores_invalides(self):
        valeurs = (
            True,
            float("nan"),
            float("inf"),
            -1,
            101
        )

        for valeur in valeurs:
            with self.subTest(
                valeur=str(valeur)
            ):
                self.assertIsNone(
                    noyau_commun.note_valide(
                        valeur
                    )
                )

    def test_09_independance_donnees(self):
        course = creer_course()
        reference = copy.deepcopy(course)

        resultats = {
            nom: self.analyser(nom, course)
            for nom in NOMS
        }

        self.assertEqual(
            course,
            reference
        )

        for nom in NOMS:
            self.assertEqual(
                resultats[nom]["moteur"],
                nom.upper()
            )

        course_modifiee = copy.deepcopy(
            course
        )

        champ_m1 = MOTEURS["m1"].CHAMP

        for cheval in course_modifiee["partants"]:
            if not cheval["non_partant"]:
                for critere in MOTEURS["m1"].POIDS:
                    cheval[champ_m1][critere] = (
                        100
                        if cheval["numero"] == 6
                        else 0
                    )

        m1_modifie = self.analyser(
            "m1",
            course_modifiee
        )

        self.assertNotEqual(
            resultats["m1"]["classement"],
            m1_modifie["classement"]
        )

        for nom in NOMS[1:]:
            with self.subTest(moteur=nom):
                autre = self.analyser(
                    nom,
                    course_modifiee
                )

                self.assertEqual(
                    resultats[nom]["classement"],
                    autre["classement"]
                )

    def test_10_resultat_reproductible(self):
        course = creer_course()

        for nom in NOMS:
            with self.subTest(moteur=nom):
                premier = self.analyser(
                    nom, course
                )

                second = self.analyser(
                    nom, course
                )

                self.assertEqual(
                    premier["classement"],
                    second["classement"]
                )

    def test_11_sortie_falsifiee_refusee(self):
        course = creer_course()

        resultat = self.analyser(
            "m1", course
        )

        falsifie = copy.deepcopy(
            resultat
        )

        falsifie["fige"] = True

        with self.assertRaises(ValueError):
            noyau_commun.verifier_sortie_analyse(
                falsifie,
                course
            )

    def test_12_identifiants_uniques(self):
        course = creer_course()

        course["partants"][1]["numero"] = 1

        valide, _ = noyau_commun.verifier_course(
            course
        )

        self.assertFalse(valide)


if __name__ == "__main__":
    unittest.main(verbosity=2)
