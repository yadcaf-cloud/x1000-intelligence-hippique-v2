import copy
import importlib
import unittest

from datetime import datetime, timedelta, timezone
from moteurs import noyau_commun


MOTEURS = ("m1", "m2", "m3", "m4", "m5")


def creer_course():
    depart = (
        datetime.now(timezone.utc) + timedelta(days=2)
    ).isoformat()

    chevaux = []

    for numero in range(1, 8):
        cheval = {
            "numero": numero,
            "nom": f"TEST_{numero}",
            "non_partant": numero == 7,
        }

        for nom in MOTEURS:
            moteur = importlib.import_module(
                f"moteurs.{nom}"
            )
            cheval[moteur.CHAMP] = {
                critere: 90 - numero * 5
                for critere in moteur.POIDS
            }

        chevaux.append(cheval)

    return {
        "id": "TEST-FONCTIONNEL-X1000",
        "localisation_france_verifiee": True,
        "depart_verifie": True,
        "depart": depart,
        "partants": chevaux,
        "nombre_partants": 6,
        "non_partants": [7],
    }


class TestFonctionnelMoteurs(unittest.TestCase):

    def test_classement_cinq_positions(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                course = creer_course()
                original = copy.deepcopy(course)

                resultat = moteur.analyser_course(course)

                self.assertEqual(
                    resultat["statut"],
                    "ANALYSE_DISPONIBLE"
                )
                self.assertEqual(
                    len(resultat["classement"]), 5
                )
                self.assertEqual(course, original)
                self.assertFalse(resultat["fige"])
                self.assertFalse(resultat["publication"])

                noyau_commun.verifier_sortie_analyse(
                    resultat, course
                )

    def test_non_partant_exclu(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                resultat = moteur.analyser_course(
                    creer_course()
                )
                numeros = [
                    c["numero"]
                    for c in resultat["classement"]
                ]
                self.assertNotIn(7, numeros)

    def test_donnees_manquantes(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                course = creer_course()

                for cheval in course["partants"]:
                    cheval.pop(moteur.CHAMP, None)

                resultat = moteur.analyser_course(course)
                self.assertEqual(
                    resultat["classement"], []
                )
                self.assertFalse(resultat["fige"])

    def test_egalites_deterministes(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                course = creer_course()

                for cheval in course["partants"]:
                    if cheval["non_partant"]:
                        continue
                    cheval[moteur.CHAMP] = {
                        critere: 70
                        for critere in moteur.POIDS
                    }

                resultat = moteur.analyser_course(course)
                numeros = [
                    c["numero"]
                    for c in resultat["classement"]
                ]
                self.assertEqual(
                    numeros, [1, 2, 3, 4, 5]
                )

    def test_score_sensible_aux_criteres(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                course = creer_course()

                initial = moteur.analyser_course(course)
                score_initial = next(
                    c["score"]
                    for c in initial["chevaux_analyses"]
                    if c["numero"] == 1
                )

                critere = next(iter(moteur.POIDS))
                course["partants"][0][moteur.CHAMP][
                    critere
                ] = 0

                nouveau = moteur.analyser_course(course)
                score_nouveau = next(
                    c["score"]
                    for c in nouveau["chevaux_analyses"]
                    if c["numero"] == 1
                )

                self.assertLess(
                    score_nouveau, score_initial
                )

    def test_sorties_interdites(self):
        for nom in MOTEURS:
            with self.subTest(moteur=nom):
                moteur = importlib.import_module(
                    f"moteurs.{nom}"
                )
                course = creer_course()
                resultat = moteur.analyser_course(course)

                for champ in ("fige", "publication"):
                    invalide = copy.deepcopy(resultat)
                    invalide[champ] = True

                    with self.assertRaises(
                        (ValueError, RuntimeError)
                    ):
                        noyau_commun.verifier_sortie_analyse(
                            invalide, course
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
