#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
TESTS LOCAUX DE SECURITE — M1 A M5

- Données entièrement synthétiques
- Vérification des cinq moteurs indépendants
- Contrôle des courses, partants et prédictions
- Contrôle de la coordination X1000
- Aucun appel PMU effectué par ce script
- Aucune publication
- Aucun FIGÉ
- Aucune modification des archives
- Aucun commit ni push

ATTENTION :
Les modules applicatifs sont importés pour être testés.
Ils doivent être vérifiés avant exécution.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path


RACINE = Path(__file__).resolve().parent

MODULES_REQUIS = (
    "validation_moteurs",
    "coordination_x1000",
)

MOTEURS_ATTENDUS = (
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
)


def verifier_modules():
    """Vérifie les modules avant tout import."""

    absents = []

    for nom in MODULES_REQUIS:
        chemin = RACINE / f"{nom}.py"

        if not chemin.is_file() or chemin.is_symlink():
            absents.append(nom)

    if absents:
        print(
            json.dumps(
                {
                    "application": "X1000 Intelligence Hippique V2",
                    "statut": "TESTS_NON_EXECUTES",
                    "raison": "MODULES_REQUIS_ABSENTS",
                    "modules_absents": absents,
                    "publication": False,
                    "fige": False,
                    "collecte_pmu_par_ce_script": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return False

    return True


def charger_modules():
    """Charge les modules applicatifs présents à la racine."""

    import validation_moteurs
    import coordination_x1000

    attributs_validation = (
        "MOTEURS",
        "ValidationErreur",
        "valider_course",
        "valider_prediction",
    )

    for nom in attributs_validation:
        if not hasattr(validation_moteurs, nom):
            raise RuntimeError(
                f"Interface manquante : validation_moteurs.{nom}"
            )

    if not hasattr(coordination_x1000, "coordonner"):
        raise RuntimeError(
            "Interface manquante : coordination_x1000.coordonner"
        )

    return validation_moteurs, coordination_x1000


def course_test():
    """Construit une course fictive et indépendante."""

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=30)
    ).isoformat()

    return {
        "id": "TEST_LOCAL_001",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart,
        "nombre_partants": 6,
        "non_partants": [],
        "partants": [
            {
                "numero": numero,
                "nom": f"CHEVAL_TEST_{numero}",
                "non_partant": False,
            }
            for numero in range(1, 7)
        ],
    }


def sorties_test():
    """Prédictions fictives des cinq moteurs."""

    return {
        moteur: [1, 2, 3, 4, 5]
        for moteur in MOTEURS_ATTENDUS
    }


def empreinte(donnees):
    """Calcule une empreinte reproductible des données."""

    contenu = json.dumps(
        donnees,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


class TestsSecuriteX1000(unittest.TestCase):
    """Batterie de tests de validation et coordination."""

    @classmethod
    def setUpClass(cls):
        validation, coordination = charger_modules()

        cls.MOTEURS = validation.MOTEURS
        cls.ValidationErreur = validation.ValidationErreur
        cls.valider_course = staticmethod(
            validation.valider_course
        )
        cls.valider_prediction = staticmethod(
            validation.valider_prediction
        )
        cls.coordonner = staticmethod(
            coordination.coordonner
        )

    def test_01_cinq_moteurs_declares(self):
        self.assertEqual(
            set(self.MOTEURS),
            set(MOTEURS_ATTENDUS),
        )

    def test_02_course_valide(self):
        self.assertEqual(
            self.valider_course(course_test()),
            set(range(1, 7)),
        )

    def test_03_france_non_verifiee(self):
        course = course_test()
        course["localisation_france_verifiee"] = False

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_04_depart_non_verifie(self):
        course = course_test()
        course["depart_verifie"] = False

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_05_depart_passe(self):
        course = course_test()

        course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(days=1)
        ).isoformat()

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_06_depart_sans_fuseau(self):
        course = course_test()
        course["depart"] = "2030-01-01T15:00:00"

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_07_depart_invalide(self):
        course = course_test()
        course["depart"] = "DATE_INVALIDE"

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_08_nombre_partants_incoherent(self):
        course = course_test()
        course["nombre_partants"] = 10

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_09_non_partants_incoherents(self):
        course = course_test()
        course["non_partants"] = [1]

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_10_numero_partant_double(self):
        course = course_test()
        course["partants"][1]["numero"] = 1

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_11_numero_partant_invalide(self):
        course = course_test()
        course["partants"][0]["numero"] = 0

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_12_non_partant_exclu(self):
        course = course_test()

        course["partants"][0]["non_partant"] = True
        course["nombre_partants"] = 5
        course["non_partants"] = [1]

        actifs = self.valider_course(course)

        self.assertNotIn(1, actifs)

        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                "M1",
                [1, 2, 3, 4, 5],
                actifs,
            )

    def test_13_doublons_prediction(self):
        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                "M1",
                [1, 1, 2, 3, 4],
                set(range(1, 7)),
            )

    def test_14_prediction_incomplete(self):
        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                "M2",
                [1, 2, 3, 4],
                set(range(1, 7)),
            )

    def test_15_moteur_inconnu(self):
        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                "M6",
                [1, 2, 3, 4, 5],
                set(range(1, 7)),
            )

    def test_16_cinq_predictions_valides(self):
        actifs = self.valider_course(course_test())

        for moteur in MOTEURS_ATTENDUS:
            with self.subTest(moteur=moteur):
                self.assertEqual(
                    self.valider_prediction(
                        moteur,
                        [1, 2, 3, 4, 5],
                        actifs,
                    ),
                    [1, 2, 3, 4, 5],
                )

    def test_17_moteur_manquant(self):
        sorties = sorties_test()
        del sorties["M5"]

        with self.assertRaises(self.ValidationErreur):
            self.coordonner(
                course_test(),
                sorties,
            )

    def test_18_coordination_sans_publication(self):
        resultat = self.coordonner(
            course_test(),
            sorties_test(),
        )

        self.assertEqual(
            resultat["statut"],
            "VALIDE_NON_PUBLIE",
        )

        self.assertEqual(
            resultat["course_id"],
            "TEST_LOCAL_001",
        )

        self.assertEqual(
            set(resultat["predictions_independantes"]),
            set(MOTEURS_ATTENDUS),
        )

        self.assertFalse(
            resultat["publication_autorisee"]
        )

        self.assertFalse(
            resultat["fige_officiel"]
        )

    def test_19_empreinte_sha256(self):
        resultat = self.coordonner(
            course_test(),
            sorties_test(),
        )

        valeur = resultat["empreinte_sha256"]

        self.assertIsInstance(valeur, str)
        self.assertEqual(len(valeur), 64)

        self.assertTrue(
            all(
                caractere in "0123456789abcdef"
                for caractere in valeur.lower()
            )
        )

    def test_20_predictions_independantes(self):
        sorties = sorties_test()

        sorties["M2"] = [5, 4, 3, 2, 1]

        resultat = self.coordonner(
            course_test(),
            sorties,
        )

        self.assertEqual(
            resultat["predictions_independantes"]["M2"],
            [5, 4, 3, 2, 1],
        )

        self.assertEqual(
            sorties["M2"],
            [5, 4, 3, 2, 1],
        )

    def test_21_entrees_non_modifiees(self):
        course = course_test()
        sorties = sorties_test()

        course_avant = empreinte(course)
        sorties_avant = empreinte(sorties)

        self.coordonner(course, sorties)

        self.assertEqual(
            empreinte(course),
            course_avant,
        )

        self.assertEqual(
            empreinte(sorties),
            sorties_avant,
        )


def main():
    if not verifier_modules():
        return 2

    try:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            TestsSecuriteX1000
        )

        resultat = unittest.TextTestRunner(
            verbosity=2,
        ).run(suite)

        return 0 if resultat.wasSuccessful() else 1

    except (ImportError, RuntimeError, OSError) as erreur:
        print(
            f"TESTS_NON_EXECUTES : {erreur}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
