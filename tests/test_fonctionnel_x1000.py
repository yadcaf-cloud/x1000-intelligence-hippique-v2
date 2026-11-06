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
                    resultat["classement"], []
                )

                with self.assertRaisesRegex(
                    ValueError, "Depart deja passe"
                ):
                    noyau_commun.verifier_sortie_analyse(
                        resultat, course
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
                    resultat["classement"], []
                )

                with self.assertRaisesRegex(
                    ValueError,
                    "Liste des non-partants incoherente"
                ):
                    noyau_commun.verifier_sortie_analyse(
                        resultat, course
                    )
