"""Tests locaux de sécurité X1000 V2.

Données synthétiques uniquement.
Aucune connexion PMU, publication ou création de FIGÉ.
"""
import unittest
from datetime import datetime, timedelta, timezone

from validation_moteurs import (
    MOTEURS,
    ValidationErreur,
    valider_course,
    valider_prediction,
)
from coordination_x1000 import coordonner


def course_test():
    """Course fictive réservée aux tests locaux."""
    return {
        "id": "TEST_LOCAL_001",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": (
            datetime.now(timezone.utc)
            + timedelta(days=1)
        ).isoformat(),
        "nombre_partants": 6,
        "non_partants": [],
        "partants": [
            {
                "numero": i,
                "nom": f"CHEVAL_TEST_{i}",
                "non_partant": False,
            }
            for i in range(1, 7)
        ],
    }


def sorties_test():
    """Sorties synthétiques des cinq moteurs."""
    return {
        moteur: [1, 2, 3, 4, 5]
        for moteur in MOTEURS
    }


class TestsValidation(unittest.TestCase):

    def test_course_valide(self):
        self.assertEqual(
            valider_course(course_test()),
            set(range(1, 7))
        )

    def test_france_non_verifiee(self):
        course = course_test()
        course["localisation_france_verifiee"] = False

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_depart_non_verifie(self):
        course = course_test()
        course["depart_verifie"] = False

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_depart_passe(self):
        course = course_test()
        course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(days=1)
        ).isoformat()

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_depart_sans_fuseau(self):
        course = course_test()
        course["depart"] = "2030-01-01T15:00:00"

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_non_partant_rejete(self):
        course = course_test()
        course["partants"][0]["non_partant"] = True
        course["nombre_partants"] = 5
        course["non_partants"] = [1]

        actifs = valider_course(course)

        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M1", [1, 2, 3, 4, 5], actifs
            )

    def test_nombre_partants_incoherent(self):
        course = course_test()
        course["nombre_partants"] = 10

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_liste_non_partants_incoherente(self):
        course = course_test()
        course["non_partants"] = [1]

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_numero_partant_double(self):
        course = course_test()
        course["partants"][1]["numero"] = 1

        with self.assertRaises(ValidationErreur):
            valider_course(course)

    def test_doublons_prediction_rejetes(self):
        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M1",
                [1, 1, 2, 3, 4],
                set(range(1, 7))
            )

    def test_prediction_incomplete(self):
        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M2",
                [1, 2, 3, 4],
                set(range(1, 7))
            )

    def test_moteur_inconnu(self):
        with self.assertRaises(ValidationErreur):
            valider_prediction(
                "M6",
                [1, 2, 3, 4, 5],
                set(range(1, 7))
            )

    def test_cinq_moteurs_valides(self):
        actifs = valider_course(course_test())

        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                self.assertEqual(
                    valider_prediction(
                        moteur,
                        [1, 2, 3, 4, 5],
                        actifs
                    ),
                    [1, 2, 3, 4, 5]
                )

    def test_moteur_manquant(self):
        sorties = sorties_test()
        del sorties["M5"]

        with self.assertRaises(ValidationErreur):
            coordonner(course_test(), sorties)

    def test_coordination_sans_publication(self):
        resultat = coordonner(
            course_test(),
            sorties_test()
        )

        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE"
        )

        self.assertEqual(
            resultat["course_id"],
            "TEST_LOCAL_001"
        )

        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(MOTEURS)
        )

        self.assertEqual(
            len(resultat["empreinte_sha256"]),
            64
        )

        self.assertFalse(
            resultat["publication_autorisee"]
        )

        self.assertFalse(
            resultat["fige_officiel"]
        )

    def test_predictions_non_modifiees(self):
        sorties = sorties_test()
        sorties["M2"] = [5, 4, 3, 2, 1]

        resultat = coordonner(
            course_test(),
            sorties
        )

        self.assertEqual(
            resultat["predictions_independantes"]["M2"],
            [5, 4, 3, 2, 1]
        )

        self.assertEqual(
            sorties["M2"],
            [5, 4, 3, 2, 1]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
