#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.5 - TESTS RENFORCES DE COORDINATION M1-M5

Compatible avec les interfaces X1000 V2.4 existantes.

Objectifs :
- Verifier les cinq moteurs independants.
- Controler les courses fictives et leurs partants.
- Tester les classements complets et partiels.
- Refuser les incoherences sportives.
- Verifier les protections FIGE et publication.
- Controler les empreintes SHA-256.
- Verifier l'absence de mutation des entrees.
- Conserver le format historique.
- Tester les sorties reelles sans donnees sportives.

Aucune collecte PMU.
Aucune prediction reelle.
Aucun FIGE automatique.
Aucune publication.
Aucune ecriture dans les archives.

Execution :
    python -m unittest -v test_coordination_x1000.py
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import re
import unittest

from datetime import datetime, timedelta, timezone

from coordination_x1000 import (
    coordonner,
    coordonner_predictions,
)

from validation_moteurs import ValidationErreur
from moteurs import noyau_commun


MOTEURS = tuple(f"M{i}" for i in range(1, 6))

STATUT_COMPLET = "VALIDE_NON_PUBLIE"
STATUT_PARTIEL = "COORDINATION_INCOMPLETE_NON_PUBLIE"

STATUT_ANALYSE = "ANALYSE_DISPONIBLE"
STATUT_INSUFFISANT = "DONNEES_INSUFFISANTES"

PROTECTIONS = (
    "publication_autorisee",
    "fige_officiel",
    "fige_automatique",
    "validation_officielle",
    "archives_modifiees",
)

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


# ============================================================
# 1. FABRICATION DE DONNEES FICTIVES
# ============================================================

def fabriquer_course():
    """Course fictive, sans source PMU."""

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=2)
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
    """Position fictive structuree."""

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
    statut=STATUT_ANALYSE,
):
    """Sortie fictive compatible avec le noyau V2.4."""

    if numeros is None:
        numeros = [1, 2, 3, 4, 5]

    positions = [
        fabriquer_position(numero, rang)
        for rang, numero in enumerate(numeros, start=1)
    ]

    complet = statut == STATUT_ANALYSE

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
    """Cinq sorties independantes."""

    return {
        moteur: fabriquer_resultat(moteur, course)
        for moteur in MOTEURS
    }


def empreinte_json(objet):
    """Empreinte canonique d'un objet JSON."""

    contenu = json.dumps(
        objet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


# ============================================================
# 2. TESTS DE COORDINATION
# ============================================================

class TestsCoordinationX1000(unittest.TestCase):

    def setUp(self):
        self.course = fabriquer_course()
        self.sorties = fabriquer_sorties(self.course)

    def coordonner_test(self):
        return coordonner(self.course, self.sorties)

    def assert_refus(self):
        """La coordination doit refuser les entrees."""

        with self.assertRaises(ValidationErreur):
            self.coordonner_test()

    def assert_protections(self, resultat):
        for cle in PROTECTIONS:
            with self.subTest(protection=cle):
                self.assertIn(cle, resultat)
                self.assertIs(resultat[cle], False)

    def assert_empreinte(self, resultat):
        empreinte = resultat["empreinte_sha256"]

        self.assertIsInstance(empreinte, str)
        self.assertRegex(empreinte, SHA256_REGEX)

    # --------------------------------------------------------
    # TESTS HISTORIQUES 01 A 20
    # --------------------------------------------------------

    def test_01_noyau_version(self):
        self.assertEqual(noyau_commun.VERSION, "2.4")

    def test_02_cinq_moteurs_importables(self):
        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                module = importlib.import_module(
                    f"moteurs.{moteur.lower()}"
                )

                self.assertEqual(module.MOTEUR, moteur)
                self.assertTrue(
                    callable(module.analyser_course)
                )

    def test_03_course_valide(self):
        valide, raison = noyau_commun.verifier_course(
            self.course
        )

        self.assertTrue(valide, raison)

    def test_04_coordination_complete(self):
        resultat = self.coordonner_test()

        self.assertEqual(
            resultat["statut"],
            STATUT_COMPLET,
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
        self.assert_protections(resultat)

    def test_05_classements_independants(self):
        self.sorties["M2"]["classement"] = [
            fabriquer_position(numero, rang)
            for rang, numero in enumerate(
                [5, 4, 3, 2, 1],
                start=1,
            )
        ]

        resultat = self.coordonner_test()
        predictions = resultat["predictions_independantes"]

        self.assertEqual(
            predictions["M1"],
            [1, 2, 3, 4, 5],
        )
        self.assertEqual(
            predictions["M2"],
            [5, 4, 3, 2, 1],
        )

    def test_06_coordination_partielle(self):
        self.sorties["M3"] = fabriquer_resultat(
            "M3",
            self.course,
            numeros=[1, 2, 3],
            statut=STATUT_INSUFFISANT,
        )

        resultat = self.coordonner_test()

        self.assertEqual(
            resultat["statut"],
            STATUT_PARTIEL,
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
        self.assert_protections(resultat)

    def test_07_doublon_refuse(self):
        self.sorties["M1"]["classement"][1][
            "numero"
        ] = 1
        self.assert_refus()

    def test_08_non_partant_refuse(self):
        self.course["partants"][0][
            "non_partant"
        ] = True
        self.course["non_partants"] = [1]
        self.course["nombre_partants"] = 5

        self.assert_refus()

    def test_09_publication_refusee(self):
        self.sorties["M4"]["publication"] = True
        self.assert_refus()

    def test_10_fige_refuse(self):
        self.sorties["M5"]["fige"] = True
        self.assert_refus()

    def test_11_moteur_manquant_refuse(self):
        del self.sorties["M5"]
        self.assert_refus()

    def test_12_course_hors_france_refusee(self):
        self.course[
            "localisation_france_verifiee"
        ] = False
        self.assert_refus()

    def test_13_course_passee_refusee(self):
        self.course["depart"] = (
            datetime.now(timezone.utc)
            - timedelta(hours=1)
        ).isoformat()

        self.assert_refus()

    def test_14_aucune_modification_entrees(self):
        course_initiale = copy.deepcopy(self.course)
        sorties_initiales = copy.deepcopy(self.sorties)

        self.coordonner_test()

        self.assertEqual(
            self.course,
            course_initiale,
        )
        self.assertEqual(
            self.sorties,
            sorties_initiales,
        )

    def test_15_empreinte_sha256(self):
        resultat1 = self.coordonner_test()
        resultat2 = self.coordonner_test()

        self.assert_empreinte(resultat1)
        self.assertEqual(
            resultat1["empreinte_sha256"],
            resultat2["empreinte_sha256"],
        )

    def test_16_sorties_sans_donnees_sportives(self):
        """
        Aucun classement ne doit etre invente
        en l'absence d'indicateurs sportifs.
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
                    STATUT_INSUFFISANT,
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
        self.assert_protections(resultat)

    def test_18_ordre_invalide_refuse(self):
        self.sorties["M2"]["classement"][0][
            "position_predite"
        ] = 3
        self.assert_refus()

    def test_19_nom_incoherent_refuse(self):
        self.sorties["M1"]["classement"][0][
            "nom"
        ] = "Cheval inconnu"
        self.assert_refus()

    def test_20_protections_finales(self):
        self.assert_protections(
            self.coordonner_test()
        )

    # --------------------------------------------------------
    # TESTS RENFORCES 21 A 40
    # --------------------------------------------------------

    def test_21_exactement_cinq_moteurs(self):
        self.assertEqual(
            MOTEURS,
            ("M1", "M2", "M3", "M4", "M5"),
        )
        self.assertEqual(len(set(MOTEURS)), 5)

    def test_22_moteur_supplementaire_refuse(self):
        self.sorties["M6"] = fabriquer_resultat(
            "M6",
            self.course,
        )
        self.assert_refus()

    def test_23_identite_moteur_incoherente(self):
        self.sorties["M2"]["moteur"] = "M1"
        self.assert_refus()

    def test_24_identifiant_course_incoherent(self):
        self.sorties["M3"]["course_id"] = (
            "AUTRE-COURSE"
        )
        self.assert_refus()

    def test_25_cinq_positions_obligatoires(self):
        self.sorties["M1"]["classement"] = (
            self.sorties["M1"]["classement"][:4]
        )
        self.assert_refus()

    def test_26_cheval_inconnu_refuse(self):
        self.sorties["M1"]["classement"][0][
            "numero"
        ] = 999
        self.assert_refus()

    def test_27_numero_booleen_refuse(self):
        self.sorties["M1"]["classement"][0][
            "numero"
        ] = True
        self.assert_refus()

    def test_28_score_invalide_refuse(self):
        for valeur in (
            -1,
            101,
            float("nan"),
            float("inf"),
            -float("inf"),
            True,
            "90",
        ):
            with self.subTest(score=repr(valeur)):
                sorties = copy.deepcopy(self.sorties)
                sorties["M1"]["classement"][0][
                    "score"
                ] = valeur

                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_29_couverture_invalide_refusee(self):
        for valeur in (
            -0.1,
            1.1,
            float("nan"),
            float("inf"),
            True,
            "1.0",
        ):
            with self.subTest(couverture=repr(valeur)):
                sorties = copy.deepcopy(self.sorties)
                sorties["M2"]["classement"][0][
                    "couverture"
                ] = valeur

                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_30_risques_format_invalide(self):
        self.sorties["M4"]["classement"][0][
            "risques"
        ] = "risque fictif"
        self.assert_refus()

    def test_31_course_non_verifiee(self):
        self.course["depart_verifie"] = False
        self.assert_refus()

    def test_32_nombre_partants_incoherent(self):
        self.course["nombre_partants"] = 100
        self.assert_refus()

    def test_33_doublon_partants_refuse(self):
        self.course["partants"][1]["numero"] = 1
        self.assert_refus()

    def test_34_date_depart_invalide(self):
        self.course["depart"] = "date-invalide"
        self.assert_refus()

    def test_35_partiel_sans_classement_invente(self):
        self.sorties["M5"] = fabriquer_resultat(
            "M5",
            self.course,
            numeros=[],
            statut=STATUT_INSUFFISANT,
        )

        resultat = self.coordonner_test()

        self.assertFalse(
            resultat["coordination_complete"]
        )
        self.assertIn(
            "M5",
            resultat["moteurs_incomplets"],
        )
        self.assertEqual(
            resultat["predictions_partielles"]["M5"],
            [],
        )
        self.assert_protections(resultat)

    def test_36_quatre_positions_partielles(self):
        self.sorties["M2"] = fabriquer_resultat(
            "M2",
            self.course,
            numeros=[2, 3, 4, 5],
            statut=STATUT_INSUFFISANT,
        )

        resultat = self.coordonner_test()

        self.assertEqual(
            resultat["predictions_partielles"]["M2"],
            [2, 3, 4, 5],
        )
        self.assertFalse(
            resultat["coordination_complete"]
        )

    def test_37_alias_coordination(self):
        resultat1 = coordonner(
            self.course,
            self.sorties,
        )
        resultat2 = coordonner_predictions(
            self.course,
            self.sorties,
        )

        self.assertEqual(resultat1, resultat2)

    def test_38_determinisme(self):
        resultats = [
            self.coordonner_test()
            for _ in range(3)
        ]

        empreintes = {
            resultat["empreinte_sha256"]
            for resultat in resultats
        }

        self.assertEqual(len(empreintes), 1)

    def test_39_json_serialisable(self):
        resultat = self.coordonner_test()

        texte = json.dumps(
            resultat,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )

        reconstruit = json.loads(texte)
        self.assertEqual(reconstruit, resultat)

    def test_40_protections_partielles(self):
        self.sorties["M1"] = fabriquer_resultat(
            "M1",
            self.course,
            numeros=[1, 2],
            statut=STATUT_INSUFFISANT,
        )

        resultat = self.coordonner_test()

        self.assertEqual(
            resultat["statut"],
            STATUT_PARTIEL,
        )
        self.assert_protections(resultat)

    # --------------------------------------------------------
    # TESTS SUPPLEMENTAIRES 41 A 50
    # --------------------------------------------------------

    def test_41_entrees_inchangees_en_cas_erreur(self):
        self.sorties["M1"]["publication"] = True

        course_avant = copy.deepcopy(self.course)
        sorties_avant = copy.deepcopy(self.sorties)

        self.assert_refus()

        self.assertEqual(self.course, course_avant)
        self.assertEqual(self.sorties, sorties_avant)

    def test_42_sorties_invalides(self):
        for sorties in (
            None,
            [],
            "M1-M5",
            {},
        ):
            with self.subTest(sorties=repr(sorties)):
                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_43_course_invalide(self):
        for course in (
            None,
            [],
            {},
            "course",
        ):
            with self.subTest(course=repr(course)):
                with self.assertRaises(
                    (ValidationErreur, TypeError, ValueError)
                ):
                    coordonner(course, self.sorties)

    def test_44_classement_historique_doublon(self):
        sorties = {
            moteur: [1, 2, 3, 4, 5]
            for moteur in MOTEURS
        }
        sorties["M3"] = [1, 1, 3, 4, 5]

        with self.assertRaises(ValidationErreur):
            coordonner(self.course, sorties)

    def test_45_classement_historique_inconnu(self):
        sorties = {
            moteur: [1, 2, 3, 4, 5]
            for moteur in MOTEURS
        }
        sorties["M4"] = [1, 2, 3, 4, 999]

        with self.assertRaises(ValidationErreur):
            coordonner(self.course, sorties)

    def test_46_classements_distincts_cinq_moteurs(self):
        ordres = {
            "M1": [1, 2, 3, 4, 5],
            "M2": [5, 4, 3, 2, 1],
            "M3": [2, 4, 1, 5, 3],
            "M4": [3, 1, 5, 2, 4],
            "M5": [4, 5, 2, 3, 1],
        }

        for moteur, numeros in ordres.items():
            self.sorties[moteur] = fabriquer_resultat(
                moteur,
                self.course,
                numeros=numeros,
            )

        resultat = self.coordonner_test()

        self.assertTrue(
            resultat["coordination_complete"]
        )
        self.assertEqual(
            resultat["predictions_independantes"],
            ordres,
        )

    def test_47_empreinte_modifiee_si_prediction_change(self):
        resultat1 = self.coordonner_test()

        self.sorties["M1"]["classement"] = [
            fabriquer_position(numero, rang)
            for rang, numero in enumerate(
                [2, 1, 3, 4, 5],
                start=1,
            )
        ]

        resultat2 = self.coordonner_test()

        self.assertNotEqual(
            resultat1["empreinte_sha256"],
            resultat2["empreinte_sha256"],
        )

    def test_48_protection_aucune_publication(self):
        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                sorties = copy.deepcopy(self.sorties)
                sorties[moteur]["publication"] = True

                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_49_protection_aucun_fige(self):
        for moteur in MOTEURS:
            with self.subTest(moteur=moteur):
                sorties = copy.deepcopy(self.sorties)
                sorties[moteur]["fige"] = True

                with self.assertRaises(ValidationErreur):
                    coordonner(self.course, sorties)

    def test_50_chaque_moteur_independant(self):
        """
        Les cinq moteurs doivent etre disponibles
        sans partager le meme module Python.
        """

        modules = [
            importlib.import_module(
                f"moteurs.{moteur.lower()}"
            )
            for moteur in MOTEURS
        ]

        self.assertEqual(
            len({id(module) for module in modules}),
            5,
        )

        for moteur, module in zip(MOTEURS, modules):
            with self.subTest(moteur=moteur):
                self.assertEqual(module.MOTEUR, moteur)
                self.assertTrue(
                    callable(module.analyser_course)
                )


# ============================================================
# 3. EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
