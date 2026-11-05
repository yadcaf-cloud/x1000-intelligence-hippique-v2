#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.5 - Tests locaux de validation M1-M5.

Aucune collecte PMU, execution des moteurs, publication, FIGE,
modification des archives ou ecriture volontaire de donnees.
Executer dans une copie temporaire isolee du depot.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MOTEURS = tuple(f"M{i}" for i in range(1, 6))
MODULES = (
    "validation_moteurs.py",
    "coordination_x1000.py",
    "moteurs/noyau_commun.py",
)


def verifier_modules():
    """Verifier existence et syntaxe sans executer les moteurs."""
    manquants = [p for p in MODULES if not (RACINE / p).is_file()]
    if manquants:
        raise FileNotFoundError("Modules manquants : " + ", ".join(manquants))
    for chemin in MODULES:
        source = (RACINE / chemin).read_text(encoding="utf-8-sig")
        ast.parse(source, filename=chemin)
    return True


def charger_modules():
    """Importer uniquement le validateur dans un environnement isole."""
    verifier_modules()
    chemin = RACINE / "validation_moteurs.py"
    spec = importlib.util.spec_from_file_location("x1000_validation_test", chemin)
    if spec is None or spec.loader is None:
        raise RuntimeError("Chargement du validateur impossible")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for nom in ("ValidationErreur", "valider_course", "valider_prediction",
                "valider_predictions_moteurs"):
        if not hasattr(module, nom):
            raise RuntimeError("Interface manquante : " + nom)
    return module


def course_test():
    """Donnees fictives : six actifs et un non-partant."""
    depart = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    return {
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart.isoformat(),
        "nombre_partants": 6,
        "partants": [
            {"numero": i, "nom": f"Cheval fictif {i}", "non_partant": i == 7}
            for i in range(1, 8)
        ],
        "non_partants": [7],
    }


def sorties_test():
    return {
        moteur: [((i + decalage - 1) % 6) + 1 for i in range(1, 6)]
        for decalage, moteur in enumerate(MOTEURS)
    }


def empreinte(donnees):
    contenu = json.dumps(donnees, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


class TestsSecuriteX1000(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validateur = charger_modules()

    def setUp(self):
        self.course = course_test()
        self.sorties = sorties_test()
        self.v = self.validateur

    def rejeter_course(self, course):
        with self.assertRaises(self.v.ValidationErreur):
            self.v.valider_course(course)

    def rejeter_prediction(self, moteur, positions, actifs=None):
        if actifs is None:
            actifs = set(range(1, 7))
        with self.assertRaises(self.v.ValidationErreur):
            self.v.valider_prediction(moteur, positions, actifs)

    def test_01_modules_et_syntaxe(self):
        self.assertTrue(verifier_modules())

    def test_02_course_synthetique(self):
        avant = copy.deepcopy(self.course)
        self.assertEqual(self.v.valider_course(self.course), set(range(1, 7)))
        self.assertEqual(self.course, avant)

    def test_03_attestations_obligatoires(self):
        for cle in ("localisation_france_verifiee", "depart_verifie"):
            for valeur in (False, None, 1, "true"):
                with self.subTest(cle=cle, valeur=valeur):
                    course = copy.deepcopy(self.course)
                    course[cle] = valeur
                    self.rejeter_course(course)

    def test_04_dates_invalides(self):
        dates = (None, "", "2026-01-01", "date-invalide",
                 (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                 (datetime.now(timezone.utc) + timedelta(days=31)).isoformat())
        for date in dates:
            with self.subTest(date=date):
                course = copy.deepcopy(self.course)
                course["depart"] = date
                self.rejeter_course(course)

    def test_05_doublon_partants(self):
        course = copy.deepcopy(self.course)
        course["partants"][1]["numero"] = 1
        self.rejeter_course(course)

    def test_06_non_partants_incoherents(self):
        course = copy.deepcopy(self.course)
        course["non_partants"] = []
        self.rejeter_course(course)

    def test_07_nombre_partants_incoherent(self):
        course = copy.deepcopy(self.course)
        course["nombre_partants"] = 7
        self.rejeter_course(course)

    def test_08_partants_types_invalides(self):
        for valeur in (True, 0, -1, "1", 1.0):
            with self.subTest(valeur=valeur):
                course = copy.deepcopy(self.course)
                course["partants"][0]["numero"] = valeur
                self.rejeter_course(course)

    def test_09_minimum_cinq_actifs(self):
        course = copy.deepcopy(self.course)
        for cheval in course["partants"][4:6]:
            cheval["non_partant"] = True
        course["non_partants"] = [5, 6, 7]
        course["nombre_partants"] = 4
        self.rejeter_course(course)

    def test_10_cinq_moteurs_independants(self):
        actifs = self.v.valider_course(self.course)
        avant = copy.deepcopy(self.sorties)
        resultat = self.v.valider_predictions_moteurs(self.sorties, actifs)
        self.assertEqual(set(resultat), set(MOTEURS))
        self.assertEqual(resultat, avant)
        self.assertEqual(self.sorties, avant)
        self.assertEqual(len({tuple(v) for v in resultat.values()}), 5)
        self.assertIsNot(resultat["M1"], self.sorties["M1"])

    def test_11_moteur_inconnu(self):
        self.rejeter_prediction("M6", [1, 2, 3, 4, 5])

    def test_12_doublons_positions(self):
        self.rejeter_prediction("M1", [1, 1, 3, 4, 5])

    def test_13_cheval_non_partant(self):
        self.rejeter_prediction("M2", [1, 2, 3, 4, 7])

    def test_14_longueur_invalide(self):
        for positions in ([], [1, 2, 3, 4], [1, 2, 3, 4, 5, 6]):
            with self.subTest(positions=positions):
                self.rejeter_prediction("M3", positions)

    def test_15_types_positions_invalides(self):
        for valeur in (True, 0, -1, "1", 1.0, None):
            with self.subTest(valeur=valeur):
                self.rejeter_prediction("M4", [valeur, 2, 3, 4, 5])

    def test_16_moteurs_incomplets(self):
        sorties = copy.deepcopy(self.sorties)
        del sorties["M5"]
        with self.assertRaises(self.v.ValidationErreur):
            self.v.valider_predictions_moteurs(sorties, set(range(1, 7)))

    def test_17_moteur_supplementaire(self):
        sorties = copy.deepcopy(self.sorties)
        sorties["M6"] = [1, 2, 3, 4, 5]
        with self.assertRaises(self.v.ValidationErreur):
            self.v.valider_predictions_moteurs(sorties, set(range(1, 7)))

    def test_18_empreinte_stable(self):
        self.assertRegex(empreinte(self.sorties), r"^[0-9a-f]{64}$")
        self.assertEqual(empreinte(self.sorties), empreinte(copy.deepcopy(self.sorties)))
        modifie = copy.deepcopy(self.sorties)
        modifie["M1"] = list(reversed(modifie["M1"]))
        self.assertNotEqual(empreinte(self.sorties), empreinte(modifie))

    def test_19_pas_de_mutation_des_entrees(self):
        course_avant = copy.deepcopy(self.course)
        sorties_avant = copy.deepcopy(self.sorties)
        actifs = self.v.valider_course(self.course)
        self.v.valider_predictions_moteurs(self.sorties, actifs)
        self.assertEqual(self.course, course_avant)
        self.assertEqual(self.sorties, sorties_avant)


def main():
    print("X1000 V2.5 - Tests securises de validation M1 a M5", flush=True)
    print("Donnees exclusivement synthetiques ; aucune validation officielle.", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestsSecuriteX1000)
    resultat = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    return 0 if resultat.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
