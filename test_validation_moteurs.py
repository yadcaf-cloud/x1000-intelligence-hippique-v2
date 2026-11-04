#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2.5
TESTS RENFORCES DE VALIDATION M1 A M5

Interfaces conservees :
- verifier_modules()
- charger_modules()
- course_test()
- sorties_test()
- empreinte(donnees)
- TestsSecuriteX1000
- main()

Modules controles :
- validation_moteurs.py
- coordination_x1000.py
- moteurs/noyau_commun.py

Regles :
- Donnees sportives exclusivement synthetiques.
- Aucun appel PMU effectue par ce fichier.
- Aucune execution volontaire des moteurs sportifs.
- Aucune publication.
- Aucun FIGE automatique ou retroactif.
- Aucune ecriture volontaire dans les archives.
- Aucun commit ni push.

Attention :
Les modules importes peuvent avoir leurs propres
effets de bord. Executer les tests dans un
environnement isole et controle.

Python 3.11 - Bibliotheque standard.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import unittest

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


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

STATUT_COMPLET = "VALIDE_NON_PUBLIE"

STATUT_PARTIEL = (
    "COORDINATION_INCOMPLETE_NON_PUBLIE"
)

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


# ============================================================
# 1. VERIFICATION DES MODULES
# ============================================================

def verifier_modules():
    """Controle la presence des modules necessaires."""

    absents = []

    chemins = {
        "validation_moteurs":
            RACINE / "validation_moteurs.py",
        "coordination_x1000":
            RACINE / "coordination_x1000.py",
        "moteurs/noyau_commun":
            RACINE / "moteurs" / "noyau_commun.py",
    }

    for nom, chemin in chemins.items():
        if not chemin.is_file() or chemin.is_symlink():
            absents.append(nom)

    if absents:
        diagnostic = {
            "application": "X1000 V2.5",
            "statut": "TESTS_NON_EXECUTES",
            "raison": "MODULES_REQUIS_ABSENTS",
            "modules_absents": absents,
            "publication": False,
            "fige": False,
            "collecte_pmu_par_ce_script": False,
        }

        print(
            json.dumps(
                diagnostic,
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )

        return False

    return True


def charger_modules():
    """Charge les interfaces applicatives existantes."""

    if not verifier_modules():
        raise RuntimeError(
            "Modules applicatifs manquants"
        )

    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))

    import validation_moteurs
    import coordination_x1000

    interfaces = (
        "MOTEURS",
        "ValidationErreur",
        "valider_course",
        "valider_prediction",
    )

    for nom in interfaces:
        if not hasattr(validation_moteurs, nom):
            raise RuntimeError(
                f"Interface absente : "
                f"validation_moteurs.{nom}"
            )

    if not hasattr(coordination_x1000, "coordonner"):
        raise RuntimeError(
            "Interface absente : "
            "coordination_x1000.coordonner"
        )

    if not isinstance(
        validation_moteurs.ValidationErreur,
        type,
    ) or not issubclass(
        validation_moteurs.ValidationErreur,
        Exception,
    ):
        raise RuntimeError(
            "ValidationErreur doit etre une exception"
        )

    for nom in (
        "valider_course",
        "valider_prediction",
    ):
        if not callable(getattr(validation_moteurs, nom)):
            raise RuntimeError(
                f"Interface non appelable : {nom}"
            )

    if not callable(coordination_x1000.coordonner):
        raise RuntimeError(
            "Interface coordonner non appelable"
        )

    return validation_moteurs, coordination_x1000


# ============================================================
# 2. DONNEES SYNTHETIQUES
# ============================================================

def course_test():
    """
    Construit une course fictive compatible avec
    l'identifiant AAAA-MM-JJ-Rn-Cn.

    Depart volontairement fixe a J+1.
    """

    depart = (
        datetime.now(timezone.utc)
        + timedelta(days=1)
    )

    date_paris = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).date()

    identifiant = (
        f"{date_paris.isoformat()}-R1-C1"
    )

    return {
        "id": identifiant,
        "course_id": identifiant,
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart.isoformat(),
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
    """Cinq classements fictifs et independants."""

    return {
        "M1": [1, 2, 3, 4, 5],
        "M2": [2, 3, 4, 5, 6],
        "M3": [3, 4, 5, 6, 1],
        "M4": [4, 5, 6, 1, 2],
        "M5": [5, 6, 1, 2, 3],
    }


def empreinte(donnees):
    """Empreinte SHA-256 reproductible."""

    contenu = json.dumps(
        donnees,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


# ============================================================
# 3. BATTERIE DE TESTS
# ============================================================

class TestsSecuriteX1000(unittest.TestCase):
    """Tests de regression et de securite X1000."""

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

        cls.valider_predictions_moteurs = staticmethod(
            validation.valider_predictions_moteurs
        )

    def verifier_course_rejetee(self, modification):
        course = course_test()
        modification(course)

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def verifier_prediction_rejetee(
        self,
        moteur,
        positions,
        actifs=None,
    ):
        if actifs is None:
            actifs = set(range(1, 7))

        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                moteur,
                positions,
                actifs,
            )

    # --------------------------------------------------------
    # A. INTERFACES ET MOTEURS
    # --------------------------------------------------------

    def test_01_cinq_moteurs_declares(self):
        self.assertEqual(
            tuple(self.MOTEURS),
            MOTEURS_ATTENDUS,
        )

    def test_02_moteurs_uniques(self):
        self.assertEqual(
            len(set(self.MOTEURS)),
            5,
        )

    def test_03_interfaces_appelables(self):
        for fonction in (
            self.valider_course,
            self.valider_prediction,
            self.coordonner,
            self.valider_predictions_moteurs,
        ):
            self.assertTrue(callable(fonction))

    # --------------------------------------------------------
    # B. VALIDATION DES COURSES
    # --------------------------------------------------------

    def test_04_course_valide(self):
        actifs = self.valider_course(course_test())

        self.assertEqual(
            actifs,
            set(range(1, 7)),
        )

    def test_05_course_non_dict(self):
        for valeur in (None, [], "", 123, True):
            with self.subTest(valeur=valeur):
                with self.assertRaises(
                    self.ValidationErreur
                ):
                    self.valider_course(valeur)

    def test_06_france_non_verifiee(self):
        self.verifier_course_rejetee(
            lambda c: c.update(
                localisation_france_verifiee=False
            )
        )

    def test_07_attestation_france_invalide(self):
        for valeur in (None, 1, "true", []):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur: c.update(
                        localisation_france_verifiee=v
                    )
                )

    def test_08_depart_non_verifie(self):
        self.verifier_course_rejetee(
            lambda c: c.update(
                depart_verifie=False
            )
        )

    def test_09_depart_passe(self):
        date = (
            datetime.now(timezone.utc)
            - timedelta(days=1)
        ).isoformat()

        self.verifier_course_rejetee(
            lambda c: c.update(depart=date)
        )

    def test_10_depart_trop_lointain(self):
        date = (
            datetime.now(timezone.utc)
            + timedelta(days=31)
        ).isoformat()

        self.verifier_course_rejetee(
            lambda c: c.update(depart=date)
        )

    def test_11_depart_sans_fuseau(self):
        self.verifier_course_rejetee(
            lambda c: c.update(
                depart="2030-01-01T15:00:00"
            )
        )

    def test_12_depart_invalide(self):
        for valeur in (
            None,
            "",
            "DATE_INVALIDE",
            123,
            "2026-13-45T12:00:00Z",
        ):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur: c.update(
                        depart=v
                    )
                )

    def test_13_identifiant_invalide(self):
        for valeur in (
            "TEST_LOCAL_001",
            "2026-01-01-R0-C1",
            "2026-01-01-R1-C0",
            "",
            123,
        ):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur: c.update(
                        id=v,
                        course_id=v,
                    )
                )

    def test_14_identifiant_date_incoherente(self):
        self.verifier_course_rejetee(
            lambda c: c.update(
                id="2020-01-01-R1-C1",
                course_id="2020-01-01-R1-C1",
            )
        )

    # --------------------------------------------------------
    # C. PARTANTS ET NON-PARTANTS
    # --------------------------------------------------------

    def test_15_nombre_partants_incoherent(self):
        self.verifier_course_rejetee(
            lambda c: c.update(nombre_partants=10)
        )

    def test_16_nombre_partants_booleen(self):
        self.verifier_course_rejetee(
            lambda c: c.update(nombre_partants=True)
        )

    def test_17_partants_non_liste(self):
        self.verifier_course_rejetee(
            lambda c: c.update(partants={})
        )

    def test_18_partant_non_dict(self):
        self.verifier_course_rejetee(
            lambda c: c["partants"].__setitem__(0, 1)
        )

    def test_19_numero_double(self):
        self.verifier_course_rejetee(
            lambda c: c["partants"][1].update(
                numero=1
            )
        )

    def test_20_numero_invalide(self):
        for valeur in (0, -1, True, 1.5, "1", None):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur:
                    c["partants"][0].update(numero=v)
                )

    def test_21_nom_cheval_invalide(self):
        for valeur in ("", "   ", None, 123):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur:
                    c["partants"][0].update(nom=v)
                )

    def test_22_statut_non_partant_invalide(self):
        for valeur in (None, 0, 1, "false"):
            with self.subTest(valeur=valeur):
                self.verifier_course_rejetee(
                    lambda c, v=valeur:
                    c["partants"][0].update(
                        non_partant=v
                    )
                )

    def test_23_non_partants_incoherents(self):
        self.verifier_course_rejetee(
            lambda c: c.update(non_partants=[1])
        )

    def test_24_non_partants_doubles(self):
        course = course_test()
        course["partants"][0]["non_partant"] = True
        course["nombre_partants"] = 5
        course["non_partants"] = [1, 1]

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    def test_25_non_partant_exclu(self):
        course = course_test()

        course["partants"][0]["non_partant"] = True
        course["nombre_partants"] = 5
        course["non_partants"] = [1]

        actifs = self.valider_course(course)

        self.assertEqual(
            actifs,
            {2, 3, 4, 5, 6},
        )

        self.verifier_prediction_rejetee(
            "M1",
            [1, 2, 3, 4, 5],
            actifs,
        )

    def test_26_moins_de_cinq_actifs(self):
        course = course_test()

        for cheval in course["partants"][:2]:
            cheval["non_partant"] = True

        course["nombre_partants"] = 4
        course["non_partants"] = [1, 2]

        with self.assertRaises(self.ValidationErreur):
            self.valider_course(course)

    # --------------------------------------------------------
    # D. PREDICTIONS INDEPENDANTES
    # --------------------------------------------------------

    def test_27_cinq_predictions_valides(self):
        actifs = set(range(1, 7))

        for moteur, positions in sorties_test().items():
            with self.subTest(moteur=moteur):
                resultat = self.valider_prediction(
                    moteur,
                    positions,
                    actifs,
                )

                self.assertEqual(resultat, positions)
                self.assertIsNot(resultat, positions)

    def test_28_moteur_inconnu(self):
        for moteur in ("M6", "", None, 1, True):
            with self.subTest(moteur=moteur):
                self.verifier_prediction_rejetee(
                    moteur,
                    [1, 2, 3, 4, 5],
                )

    def test_29_prediction_incomplete(self):
        self.verifier_prediction_rejetee(
            "M1",
            [1, 2, 3, 4],
        )

    def test_30_prediction_trop_longue(self):
        self.verifier_prediction_rejetee(
            "M1",
            [1, 2, 3, 4, 5, 6],
        )

    def test_31_doublons_prediction(self):
        self.verifier_prediction_rejetee(
            "M2",
            [1, 1, 2, 3, 4],
        )

    def test_32_numero_prediction_invalide(self):
        for valeur in (
            True,
            0,
            -1,
            1.5,
            "1",
            None,
        ):
            with self.subTest(valeur=valeur):
                self.verifier_prediction_rejetee(
                    "M3",
                    [valeur, 2, 3, 4, 5],
                )

    def test_33_cheval_inconnu(self):
        self.verifier_prediction_rejetee(
            "M4",
            [1, 2, 3, 4, 99],
        )

    def test_34_prediction_non_liste(self):
        for valeur in (
            None,
            (1, 2, 3, 4, 5),
            "12345",
            {1, 2, 3, 4, 5},
        ):
            with self.subTest(valeur=str(valeur)):
                self.verifier_prediction_rejetee(
                    "M5",
                    valeur,
                )

    def test_35_actifs_invalides(self):
        for actifs in (
            None,
            [],
            {1, 2, 3, 4},
            {True, 2, 3, 4, 5},
        ):
            with self.subTest(actifs=str(actifs)):
                self.verifier_prediction_rejetee(
                    "M1",
                    [1, 2, 3, 4, 5],
                    actifs,
                )

    def test_36_validation_groupee(self):
        actifs = set(range(1, 7))
        sorties = sorties_test()

        resultat = self.valider_predictions_moteurs(
            sorties,
            actifs,
        )

        self.assertEqual(resultat, sorties)
        self.assertIsNot(resultat, sorties)

        for moteur in MOTEURS_ATTENDUS:
            self.assertIsNot(
                resultat[moteur],
                sorties[moteur],
            )

    def test_37_validation_groupee_incomplete(self):
        sorties = sorties_test()
        del sorties["M5"]

        with self.assertRaises(self.ValidationErreur):
            self.valider_predictions_moteurs(
                sorties,
                set(range(1, 7)),
            )

    def test_38_validation_groupee_moteur_inconnu(self):
        sorties = sorties_test()
        sorties["M6"] = [1, 2, 3, 4, 5]

        with self.assertRaises(self.ValidationErreur):
            self.valider_predictions_moteurs(
                sorties,
                set(range(1, 7)),
            )

    def test_39_validation_groupee_partielle(self):
        sorties = sorties_test()
        del sorties["M5"]

        resultat = self.valider_predictions_moteurs(
            sorties,
            set(range(1, 7)),
            exiger_cinq_moteurs=False,
        )

        self.assertEqual(set(resultat), set(sorties))

    # --------------------------------------------------------
    # E. COORDINATION CENTRALE
    # --------------------------------------------------------

    def test_40_moteur_manquant(self):
        sorties = sorties_test()
        del sorties["M5"]

        with self.assertRaises(self.ValidationErreur):
            self.coordonner(
                course_test(),
                sorties,
            )

    def test_41_moteur_supplementaire(self):
        sorties = sorties_test()
        sorties["M6"] = [1, 2, 3, 4, 5]

        with self.assertRaises(self.ValidationErreur):
            self.coordonner(
                course_test(),
                sorties,
            )

    def test_42_coordination_complete(self):
        course = course_test()
        sorties = sorties_test()

        resultat = self.coordonner(course, sorties)

        self.assertEqual(
            resultat["statut"],
            STATUT_COMPLET,
        )

        self.assertEqual(
            resultat["course_id"],
            course["id"],
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
            set(MOTEURS_ATTENDUS),
        )

        self.assertEqual(
            resultat["moteurs_incomplets"],
            [],
        )

    def test_43_predictions_independantes(self):
        sorties = sorties_test()

        resultat = self.coordonner(
            course_test(),
            sorties,
        )

        predictions = resultat[
            "predictions_independantes"
        ]

        self.assertEqual(predictions, sorties)

        self.assertEqual(
            set(predictions),
            set(MOTEURS_ATTENDUS),
        )

        for moteur in MOTEURS_ATTENDUS:
            with self.subTest(moteur=moteur):
                self.assertIsNot(
                    predictions[moteur],
                    sorties[moteur],
                )

    def test_44_analyses_independantes(self):
        resultat = self.coordonner(
            course_test(),
            sorties_test(),
        )

        analyses = resultat[
            "analyses_independantes"
        ]

        self.assertEqual(
            set(analyses),
            set(MOTEURS_ATTENDUS),
        )

        for moteur in MOTEURS_ATTENDUS:
            with self.subTest(moteur=moteur):
                self.assertEqual(
                    analyses[moteur]["moteur"],
                    moteur,
                )

                self.assertEqual(
                    analyses[moteur]["statut"],
                    "ANALYSE_DISPONIBLE",
                )

    def test_45_aucune_publication_ni_fige(self):
        resultat = self.coordonner(
            course_test(),
            sorties_test(),
        )

        indicateurs = (
            "publication_autorisee",
            "fige_officiel",
            "fige_automatique",
            "validation_officielle",
            "archives_modifiees",
        )

        for cle in indicateurs:
            with self.subTest(indicateur=cle):
                self.assertIn(cle, resultat)
                self.assertIs(resultat[cle], False)

    def test_46_empreinte_sha256(self):
        resultat = self.coordonner(
            course_test(),
            sorties_test(),
        )

        valeur = resultat["empreinte_sha256"]

        self.assertIsInstance(valeur, str)
        self.assertRegex(valeur, SHA256_REGEX)

    def test_47_empreinte_stable(self):
        course = course_test()
        sorties = sorties_test()

        premier = self.coordonner(
            copy.deepcopy(course),
            copy.deepcopy(sorties),
        )

        second = self.coordonner(
            copy.deepcopy(course),
            copy.deepcopy(sorties),
        )

        self.assertEqual(
            premier["empreinte_sha256"],
            second["empreinte_sha256"],
        )

    def test_48_empreinte_sensible_aux_classements(self):
        course = course_test()
        sorties = sorties_test()

        premier = self.coordonner(
            copy.deepcopy(course),
            copy.deepcopy(sorties),
        )

        sorties["M2"] = [6, 5, 4, 3, 2]

        second = self.coordonner(
            copy.deepcopy(course),
            sorties,
        )

        self.assertNotEqual(
            premier["empreinte_sha256"],
            second["empreinte_sha256"],
        )

    def test_49_entrees_non_modifiees(self):
        course = course_test()
        sorties = sorties_test()

        avant_course = copy.deepcopy(course)
        avant_sorties = copy.deepcopy(sorties)

        self.coordonner(course, sorties)

        self.assertEqual(course, avant_course)
        self.assertEqual(sorties, avant_sorties)

    def test_50_rejet_prediction_invalide(self):
        sorties = sorties_test()
        sorties["M3"] = [1, 1, 2, 3, 4]

        with self.assertRaises(self.ValidationErreur):
            self.coordonner(
                course_test(),
                sorties,
            )

    def test_51_rejet_non_partant_coordination(self):
        course = course_test()

        course["partants"][0]["non_partant"] = True
        course["nombre_partants"] = 5
        course["non_partants"] = [1]

        with self.assertRaises(self.ValidationErreur):
            self.coordonner(
                course,
                sorties_test(),
            )

    # --------------------------------------------------------
    # F. TESTS DE REPRODUCTIBILITE
    # --------------------------------------------------------

    def test_52_empreinte_locale_stable(self):
        donnees = {
            "moteurs": list(MOTEURS_ATTENDUS),
            "positions": [1, 2, 3, 4, 5],
        }

        self.assertEqual(
            empreinte(donnees),
            empreinte(copy.deepcopy(donnees)),
        )

    def test_53_empreinte_locale_modification(self):
        a = {"M1": [1, 2, 3, 4, 5]}
        b = {"M1": [5, 4, 3, 2, 1]}

        self.assertNotEqual(
            empreinte(a),
            empreinte(b),
        )

    def test_54_course_retour_independant(self):
        course = course_test()
        avant = copy.deepcopy(course)

        actifs = self.valider_course(course)

        self.assertEqual(course, avant)

        actifs.remove(1)

        self.assertEqual(
            len(course["partants"]),
            6,
        )

    def test_55_coordination_reproductible(self):
        course = course_test()
        sorties = sorties_test()

        a = self.coordonner(
            copy.deepcopy(course),
            copy.deepcopy(sorties),
        )

        b = self.coordonner(
            copy.deepcopy(course),
            copy.deepcopy(sorties),
        )

        self.assertEqual(
            a["predictions_independantes"],
            b["predictions_independantes"],
        )

        self.assertEqual(
            a["empreinte_sha256"],
            b["empreinte_sha256"],
        )


# ============================================================
# 4. EXECUTION
# ============================================================

def main():
    """Execute les tests et retourne un code de sortie."""

    if not verifier_modules():
        return 2

    try:
        suite = (
            unittest.defaultTestLoader
            .loadTestsFromTestCase(
                TestsSecuriteX1000
            )
        )

        print(
            "\nX1000 V2.5 - TESTS RENFORCES M1 A M5",
            flush=True,
        )

        print(
            "Mode : donnees synthetiques",
            flush=True,
        )

        resultat = unittest.TextTestRunner(
            verbosity=2,
            stream=sys.stdout,
        ).run(suite)

        statut = (
            "SUCCES"
            if resultat.wasSuccessful()
            else "ECHEC"
        )

        bilan = {
            "application": "X1000 V2.5",
            "statut": statut,
            "tests_executes": resultat.testsRun,
            "echecs": len(resultat.failures),
            "erreurs": len(resultat.errors),
            "ignores": len(resultat.skipped),
            "publication_par_ce_script": False,
            "fige_par_ce_script": False,
            "collecte_pmu_par_ce_script": False,
        }

        print(
            json.dumps(
                bilan,
                ensure_ascii=False,
                indent=2,
            )
        )

        return (
            0 if resultat.wasSuccessful() else 1
        )

    except (
        ImportError,
        RuntimeError,
        OSError,
    ) as erreur:

        print(
            f"TESTS_NON_EXECUTES : {erreur}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
