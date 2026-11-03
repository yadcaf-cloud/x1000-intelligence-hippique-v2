"""X1000 V2 - M1 : statistiques et performances."""

from datetime import datetime, timezone


class MoteurM1:
    """Moteur independant de classement statistique."""

    nom = "M1"
    version = "2.0"

    def analyser(self, course):
        if not isinstance(course, dict):
            raise ValueError("Course invalide")

        if course.get("localisation_france_verifiee") is not True:
            raise ValueError("Course en France non verifiee")

        if course.get("depart_verifie") is not True:
            raise ValueError("Depart non verifie")

        partants = course.get("partants")
        if not isinstance(partants, list):
            raise ValueError("Liste des partants absente")

        resultats = []
        numeros = set()

        for cheval in partants:
            if not isinstance(cheval, dict):
                raise ValueError("Cheval invalide")

            numero = cheval.get("numero")
            nom = cheval.get("nom")

            if type(numero) is not int or numero <= 0:
                raise ValueError("Numero invalide")
            if numero in numeros:
                raise ValueError("Numero en double")
            if not isinstance(nom, str) or not nom.strip():
                raise ValueError("Nom de cheval invalide")

            numeros.add(numero)

            if cheval.get("non_partant") is True:
                continue

            statistiques = cheval.get("statistiques")
            if not isinstance(statistiques, dict):
                continue

            criteres = (
                "forme",
                "regularite",
                "distance",
                "parcours",
                "performance",
            )

            valeurs = []
            for critere in criteres:
                valeur = statistiques.get(critere)
                if type(valeur) not in (int, float):
                    break
                if not 0 <= valeur <= 100:
                    break
                valeurs.append(float(valeur))

            if len(valeurs) != len(criteres):
                continue

            score = round(sum(valeurs) / len(valeurs), 2)

            resultats.append({
                "numero": numero,
                "nom": nom,
                "score": score,
            })

        resultats.sort(
            key=lambda x: (-x["score"], x["numero"])
        )

        return {
            "moteur": self.nom,
            "version": self.version,
            "course_id": course.get("id"),
            "analyse_a": datetime.now(
                timezone.utc
            ).isoformat(),
            "statut": (
                "ANALYSE_DISPONIBLE"
                if len(resultats) >= 5
                else "DONNEES_INSUFFISANTES"
            ),
            "classement": resultats[:5]
            if len(resultats) >= 5 else [],
            "chevaux_evalues": len(resultats),
            "fige": False,
        }
