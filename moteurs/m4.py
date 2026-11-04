#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M4 : TACTIQUE ET SCENARIOS

Moteur sportif independant M4.

- Analyse des courses PMU en France.
- Validation technique par le noyau commun.
- Analyse des partants actifs uniquement.
- Six criteres tactiques independants.
- Cinq positions predites si possible.
- Classement partiel si donnees insuffisantes.
- Detection des risques tactiques.
- Aucune donnee sportive inventee.
- Aucune collecte PMU.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune modification des archives.

Execution en lecture seule :
    python -m moteurs.m4 --input course.json
"""

from __future__ import annotations

import math
import sys
from typing import Any


# ============================================================
# 1. IMPORT DU NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


analyse_commune = noyau_commun.analyser_course
execution_commune = noyau_commun.executer


# ============================================================
# 2. IDENTITE ET CONFIGURATION M4
# ============================================================

MOTEUR = "M4"
VERSION = "2.4"
CHAMP = "indicateurs_m4"

COUVERTURE_MIN = 0.65
SEUIL_RISQUE = 40.0

POIDS = {
    "vitesse_depart": 0.15,
    "positionnement": 0.20,
    "adaptation_rythme": 0.20,
    "endurance": 0.20,
    "aptitude_parcours": 0.15,
    "fiabilite_tactique": 0.10,
}

LIBELLES_RISQUES = {
    "vitesse_depart": "Depart potentiellement difficile",
    "positionnement": "Positionnement defavorable",
    "adaptation_rythme": "Adaptation au rythme incertaine",
    "endurance": "Endurance potentiellement insuffisante",
    "aptitude_parcours": "Aptitude au parcours faible",
    "fiabilite_tactique": "Fiabilite tactique faible",
}

STATUTS_ATTENDUS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 3. VERIFICATION DE LA CONFIGURATION
# ============================================================

def verifier_configuration() -> None:
    """Controle la configuration et le noyau commun."""

    version_noyau = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if version_noyau != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M4={VERSION}, noyau={version_noyau}"
        )

    if not callable(analyse_commune):
        raise RuntimeError(
            "Analyse commune indisponible"
        )

    if not callable(execution_commune):
        raise RuntimeError(
            "Execution commune indisponible"
        )

    if (
        not isinstance(CHAMP, str)
        or not CHAMP.strip()
    ):
        raise RuntimeError(
            "Champ M4 invalide"
        )

    if not isinstance(POIDS, dict) or not POIDS:
        raise RuntimeError(
            "Ponderations M4 absentes"
        )

    for critere, poids in POIDS.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise RuntimeError(
                "Critere M4 invalide"
            )

        if (
            type(poids) not in (int, float)
            or not math.isfinite(poids)
            or poids <= 0
        ):
            raise RuntimeError(
                f"Poids M4 invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "La somme des poids M4 doit etre egale a 1"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Seuil de couverture M4 invalide"
        )

    if (
        type(SEUIL_RISQUE) not in (int, float)
        or not math.isfinite(SEUIL_RISQUE)
        or not 0 <= SEUIL_RISQUE <= 100
    ):
        raise RuntimeError(
            "Seuil de risque M4 invalide"
        )

    if set(LIBELLES_RISQUES) != set(POIDS):
        raise RuntimeError(
            "Criteres de risques M4 incoherents"
        )

    statuts_noyau = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if (
        not isinstance(
            statuts_noyau,
            (set, frozenset, tuple, list),
        )
        or set(statuts_noyau) != STATUTS_ATTENDUS
    ):
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


def verifier_noyau() -> None:
    """Alias de compatibilite."""

    verifier_configuration()


# ============================================================
# 4. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """Accepte uniquement les notes de 0 a 100."""

    if type(valeur) not in (int, float):
        return None

    try:
        valeur = float(valeur)
    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return None

    if not math.isfinite(valeur):
        return None

    if not 0 <= valeur <= 100:
        return None

    return valeur


# ============================================================
# 5. IDENTIFICATION DES RISQUES TACTIQUES
# ============================================================

def identifier_risques(
    criteres: dict,
) -> list[str]:
    """
    Signale les fragilites tactiques documentees.

    Une donnee absente ne devient pas
    automatiquement un risque.
    """

    risques = []

    for critere, libelle in LIBELLES_RISQUES.items():

        valeur = note_valide(
            criteres.get(critere)
        )

        if (
            valeur is not None
            and valeur < SEUIL_RISQUE
        ):
            risques.append(libelle)

    return risques


# ============================================================
# 6. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(
    resultat: Any,
) -> None:
    """Refuse les sorties incompatibles du noyau."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat M4 non conforme"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identite du moteur incoherente"
        )

    if resultat.get("statut") not in STATUTS_ATTENDUS:
        raise RuntimeError(
            "Statut M4 invalide"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGE interdit dans M4"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans M4"
        )

    for cle in (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    ):

        if not isinstance(
            resultat.get(cle),
            list,
        ):
            raise RuntimeError(
                f"Champ M4 invalide : {cle}"
            )

        for entree in resultat[cle]:

            if not isinstance(entree, dict):
                raise RuntimeError(
                    f"Entree M4 invalide : {cle}"
                )

    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]
    statut = resultat["statut"]

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M4 obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel M4 incoherent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour "
            "une course non analysable"
        )

    numeros_analyses = set()

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros_analyses
        ):
            raise RuntimeError(
                "Numero analyse M4 invalide"
            )

        numeros_analyses.add(numero)

        score = analyse.get("score")

        if (
            score is not None
            and note_valide(score) is None
        ):
            raise RuntimeError(
                "Score analyse M4 invalide"
            )

    for cle in (
        "classement",
        "classement_partiel",
    ):

        numeros_classes = set()

        for rang, position in enumerate(
            resultat[cle],
            start=1,
        ):

            numero = position.get("numero")

            if (
                type(numero) is not int
                or numero not in numeros_analyses
                or numero in numeros_classes
            ):
                raise RuntimeError(
                    "Classement M4 incoherent"
                )

            numeros_classes.add(numero)

            if (
                type(position.get("position_predite"))
                is not int
                or position["position_predite"] != rang
            ):
                raise RuntimeError(
                    "Position predite M4 invalide"
                )

            if note_valide(
                position.get("score")
            ) is None:
                raise RuntimeError(
                    "Score de classement M4 invalide"
                )


# ============================================================
# 7. ENRICHISSEMENT DES ANALYSES
# ============================================================

def enrichir_analyses(
    resultat: dict,
) -> None:
    """
    Ajoute les risques propres a M4.

    Les scores restent ceux du noyau commun.
    Aucun score n'est recalcule ou invente.
    """

    risques_tactiques = []

    for analyse in resultat["chevaux_analyses"]:

        criteres = analyse.get("criteres")

        if not isinstance(criteres, dict):
            raise RuntimeError(
                "Criteres M4 invalides"
            )

        risques = identifier_risques(
            criteres
        )

        analyse["score_m4"] = analyse.get("score")
        analyse["risques"] = risques

        if risques:
            risques_tactiques.append({
                "numero": analyse["numero"],
                "nom": analyse["nom"],
                "risques": list(risques),
            })

    resultat["risques_tactiques"] = risques_tactiques
    resultat["alertes_risques"] = [
        dict(entree)
        for entree in risques_tactiques
    ]


# ============================================================
# 8. ENRICHISSEMENT DU CLASSEMENT
# ============================================================

def enrichir_classement(
    resultat: dict,
) -> None:
    """Ajoute les informations tactiques au classement."""

    analyses = {
        analyse["numero"]: analyse
        for analyse in resultat["chevaux_analyses"]
    }

    scores = [
        analyse["score"]
        for analyse in analyses.values()
        if analyse.get("score") is not None
    ]

    for cle in (
        "classement",
        "classement_partiel",
    ):

        for position in resultat[cle]:

            numero = position["numero"]
            analyse = analyses[numero]

            score = position["score"]

            egalite = sum(
                autre_score == score
                for autre_score in scores
            ) > 1

            position["score_m4"] = score
            position["risques"] = list(
                analyse["risques"]
            )
            position["egalite_score"] = egalite


# ============================================================
# 9. ANALYSE SPORTIVE INDEPENDANTE M4
# ============================================================

def analyser_course(
    course: Any,
) -> dict:
    """
    Analyse tactique M4.

    Le noyau commun assure les validations
    techniques et calcule les scores M4
    avec les six ponderations propres au moteur.

    M4 ajoute ses alertes tactiques sans
    modifier les scores ni les positions.
    """

    verifier_configuration()

    resultat = analyse_commune(
        course=course,
        moteur=MOTEUR,
        poids=POIDS,
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat)

    resultat["risques_tactiques"] = []
    resultat["alertes_risques"] = []

    if resultat["statut"] == "NON_ANALYSABLE":
        return resultat

    enrichir_analyses(resultat)
    enrichir_classement(resultat)

    resultat["nombre_partants_actifs"] = len(
        resultat["chevaux_analyses"]
    )

    resultat["nombre_chevaux_admissibles"] = sum(
        analyse.get("score") is not None
        for analyse in resultat["chevaux_analyses"]
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 10. INTERFACE COORDINATEUR X1000
# ============================================================

def analyser_course_m4(
    course: Any,
) -> dict:
    """Point d'entree explicite du moteur M4."""

    return analyser_course(course)


class MoteurM4:
    """Moteur tactique independant M4."""

    nom = MOTEUR
    version = VERSION

    def analyser(
        self,
        course: Any,
    ) -> dict:
        return analyser_course(course)


# ============================================================
# 11. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    fonction_analyse=None,
) -> int:
    """Interface historique compatible."""

    verifier_configuration()

    if fonction_analyse is None:
        fonction_analyse = analyser_course

    if not callable(fonction_analyse):
        raise TypeError(
            "Fonction d'analyse M4 invalide"
        )

    return execution_commune(
        fonction_analyse
    )


def main() -> int:
    """
    Execution :
        python -m moteurs.m4 --input course.json

    Codes de sortie :
        0 : analyse disponible
        2 : donnees insuffisantes ou non analysable
        1 : erreur technique
    """

    try:
        return executer(
            analyser_course
        )

    except (
        RuntimeError,
        ValueError,
        TypeError,
        OverflowError,
    ) as erreur:

        print(
            f"Erreur M4 : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 12. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
