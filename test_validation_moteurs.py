    def verifier_prediction_rejetee(
        self,
        moteur,
        positions,
        actifs=Ellipsis,
    ):
        """
        X1000 V2.5 - Correction du test 35.

        Distingue :
        - Argument actifs absent : ensemble valide par defaut.
        - actifs=None : valeur invalide a rejeter.
        - Liste invalide : rejet obligatoire.
        - Ensemble insuffisant : rejet obligatoire.
        - Numeros booleens : rejet obligatoire.

        Aucune modification des moteurs.
        Aucune collecte PMU.
        Aucune publication.
        Aucun FIGE.
        Aucune ecriture dans les archives.
        """

        if actifs is Ellipsis:
            actifs = set(range(1, 7))

        with self.assertRaises(self.ValidationErreur):
            self.valider_prediction(
                moteur,
                positions,
                actifs,
            )
