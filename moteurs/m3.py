#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M3 : OUTSIDERS ET FAVORIS VULNERABLES

Analyse sportive independante.
Detection des outsiders et favoris a examiner.

Garanties :
- Courses PMU physiquement disputees en France.
- Donnees sportives documentees.
- Cinq positions predites si donnees suffisantes.
- Moteur M3 independant de M1, M2, M4 et M5.
- Aucune donnee inventee.
- Aucun FIGE automatique ou retroactif.
- Aucune publication.
- Aucune collecte PMU.
- Aucune modification des archives.

Les validations techniques sont deleguees
au noyau commun X1000 V2.4.
"""

from __future__ import annotations

import math
import sys

from datetime import datetime, timezone
from typing import Any


# ============================================================
# 1. IMPORT DU NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun


analyse_commune = noyau_commun.analyser_course
executer = noyau_commun.executer


# ============================================================
# 2. IDENTITE ET CONFIGURATION M3
# ============================================================

MOTEUR = "M3"
VERSION = "2.4"

CHAMP = "indicateurs_m3"

COUVERTURE_MIN = 0.65

POIDS = {
    "forme": 0.25,
    "progression": 0.25,
    "aptitude_parcours": 0.20,
    "regularite": 0.15,
    "potentiel_surprise": 0.15,
}

SEUIL_COTE_OUTSIDER = 10.0
SEUIL_SCORE_OUTSIDER = 70.0

SEUIL_COTE_FAVORI = 4.0
SEUIL_SCORE_FAVORI_FAIBLE = 55.0


# ============================================================
# 3. VERIFICATION DU NOYAU ET DE LA CONFIGURATION
# ============================================================

def verifier_noyau() -> None:
    """Verifie la compatibilite du moteur M3."""

    version = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if version != VERSION:
        raise RuntimeError(
            "Version du noyau incompatible : "
            f"M3={VERSION}, noyau={version}"
        )

    if not callable(analyse_commune):
        raise RuntimeError(
            "Analyse commune indisponible"
        )

    if not callable(executer):
        raise RuntimeError(
            "Execution commune indisponible"
        )

    if not isinstance(CHAMP, str) or not CHAMP.strip():
        raise RuntimeError(
            "Champ M3 invalide"
        )

    if not isinstance(POIDS, dict) or not POIDS:
        raise RuntimeError(
            "Ponderations M3 absentes"
        )

    for critere, poids in POIDS.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise RuntimeError(
                "Critere M3 invalide"
            )

        if (
            type(poids) not in (int, float)
            or not math.isfinite(poids)
            or poids <= 0
        ):
            raise RuntimeError(
                f"Poids M3 invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "Somme des ponderations M3 invalide"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Couverture minimale M3 invalide"
        )

    statuts = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    statuts_attendus = {
        "ANALYSE_DISPONIBLE",
        "DONNEES_INSUFFISANTES",
        "NON_ANALYSABLE",
    }

    if (
        not isinstance(statuts, (set, frozenset))
        or statuts != statuts_attendus
    ):
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


# ============================================================
# 4. VALIDATION DES DATES
# ============================================================

def lire_date(
    valeur: Any,
) -> datetime | None:
    """Lit une date ISO avec fuseau horaire."""

    if not isinstance(valeur, str):
        return None

    try:
        date = datetime.fromisoformat(
            valeur.strip().replace(
                "Z",
                "+00:00",
            )
        )

        if date.utcoffset() is None:
            return None

        return date.astimezone(timezone.utc)

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return None


# ============================================================
# 5. VALIDATION DES COTES
# ============================================================

def verifier_cote(
    cheval: dict,
    depart: str,
) -> tuple[
    float | None,
    str | None,
    str | None,
]:
    """
    Accepte uniquement une cote :
    - numerique et finie ;
    - superieure a 1 ;
    - avec source renseignee ;
    - horodatee avant le depart ;
    - non datee dans le futur.

    La presence d'une source ne constitue pas
    une authentification independante.
    """

    cote = cheval.get("cote")
    source = cheval.get("cote_source")
    collecte_a = cheval.get("cote_collectee_a")

    if type(cote) not in (int, float):
        return None, None, None

    try:
        cote = float(cote)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None, None, None

    if not math.isfinite(cote) or cote <= 1:
        return None, None, None

    if (
        not isinstance(source, str)
        or not source.strip()
    ):
        return None, None, None

    date_cote = lire_date(collecte_a)
    date_depart = lire_date(depart)

    if date_cote is None or date_depart is None:
        return None, None, None

    maintenant = datetime.now(timezone.utc)

    if date_cote > maintenant:
        return None, None, None

    if date_cote >= date_depart:
        return None, None, None

    return (
        cote,
        source.strip(),
        collecte_a,
    )


# ============================================================
# 6. VALIDATION DES SCORES
# ============================================================

def verifier_score(
    valeur: Any,
) -> bool:
    """Verifie un score compris entre 0 et 100."""

    if valeur is None:
        return True

    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 100
    )


# ============================================================
# 7. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(
    resultat: Any,
) -> None:
    """Refuse toute sortie commune incoherente."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Resultat commun non conforme"
        )

    statut = resultat.get("statut")

    if statut not in noyau_commun.STATUTS_VALIDES:
        raise RuntimeError(
            "Statut M3 invalide"
        )

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identite du moteur incoherente"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGE interdit dans M3"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans M3"
        )

    champs = (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    )

    for cle in champs:

        if not isinstance(
            resultat.get(cle),
            list,
        ):
            raise RuntimeError(
                f"Champ commun invalide : {cle}"
            )

        for entree in resultat[cle]:

            if not isinstance(entree, dict):
                raise RuntimeError(
                    f"Entree invalide dans {cle}"
                )

            if "score" not in entree:
                raise RuntimeError(
                    f"Score absent dans {cle}"
                )

            if not verifier_score(
                entree["score"]
            ):
                raise RuntimeError(
                    f"Score invalide dans {cle}"
                )

    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]

    if statut == "ANALYSE_DISPONIBLE":

        if len(classement) != 5 or partiel:
            raise RuntimeError(
                "Cinq positions M3 obligatoires"
            )

    elif statut == "DONNEES_INSUFFISANTES":

        if classement or len(partiel) >= 5:
            raise RuntimeError(
                "Classement partiel M3 incoherent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour "
            "une course non analysable"
        )

    for cle in (
        "classement",
        "classement_partiel",
    ):

        numeros = set()

        for position_attendue, entree in enumerate(
            resultat[cle],
            start=1,
        ):

            numero = entree.get("numero")

            if (
                type(numero) is not int
                or numero <= 0
            ):
                raise RuntimeError(
                    "Numero de cheval invalide"
                )

            if numero in numeros:
                raise RuntimeError(
                    "Cheval classe plusieurs fois"
                )

            numeros.add(numero)

            if (
                type(entree.get("position_predite"))
                is not int
                or entree["position_predite"]
                != position_attendue
            ):
                raise RuntimeError(
                    "Ordre des positions M3 invalide"
                )


# ============================================================
# 8. ANALYSE SPORTIVE INDEPENDANTE M3
# ============================================================

def analyser_course(
    course: Any,
) -> dict:
    """
    Analyse M3 :
    - evaluation des indicateurs ;
    - classement de cinq chevaux si possible ;
    - recherche des outsiders potentiels ;
    - detection des favoris vulnerables.

    Aucune prediction n'est inventee.
    """

    verifier_noyau()

    resultat = analyse_commune(
        course=course,
        moteur=MOTEUR,
        poids=POIDS,
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat)

    if resultat["statut"] == "NON_ANALYSABLE":
        return resultat

    if not isinstance(course, dict):
        raise RuntimeError(
            "Course M3 invalide"
        )

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise RuntimeError(
            "Partants M3 invalides"
        )

    chevaux = {}
    numeros_tous = set()

    for cheval in partants:

        if not isinstance(cheval, dict):
            raise RuntimeError(
                "Cheval M3 invalide"
            )

        numero = cheval.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
        ):
            raise RuntimeError(
                "Numero M3 invalide"
            )

        if numero in numeros_tous:
            raise RuntimeError(
                "Numero de cheval en double"
            )

        numeros_tous.add(numero)

        if type(cheval.get("non_partant")) is not bool:
            raise RuntimeError(
                "Statut non-partant invalide"
            )

        if not cheval["non_partant"]:
            chevaux[numero] = cheval

    resultat["outsiders_potentiels"] = []
    resultat["favoris_a_examiner"] = []

    numeros_analyses = set()

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse.get("numero")

        if numero not in chevaux:
            raise RuntimeError(
                "Cheval analyse absent "
                "des partants actifs"
            )

        if numero in numeros_analyses:
            raise RuntimeError(
                "Cheval analyse plusieurs fois"
            )

        numeros_analyses.add(numero)

        cheval = chevaux[numero]

        if (
            not isinstance(analyse.get("nom"), str)
            or not analyse["nom"].strip()
        ):
            raise RuntimeError(
                "Nom analyse invalide"
            )

        if analyse["nom"] != cheval.get("nom"):
            raise RuntimeError(
                "Nom du cheval incoherent"
            )

        cote, source, collecte_a = verifier_cote(
            cheval,
            course.get("depart"),
        )

        analyse["cote"] = cote
        analyse["cote_source"] = source
        analyse["cote_collectee_a"] = collecte_a

        analyse["score_m3"] = analyse["score"]

        if (
            cote is None
            and cheval.get("cote") is not None
        ):
            analyse["cote_ignoree"] = (
                "Cote invalide ou provenance "
                "insuffisante"
            )

        score = analyse["score"]

        if score is None or cote is None:
            continue

        # ----------------------------------------
        # OUTSIDERS POTENTIELS
        # ----------------------------------------

        if (
            cote >= SEUIL_COTE_OUTSIDER
            and score >= SEUIL_SCORE_OUTSIDER
        ):

            resultat["outsiders_potentiels"].append({
                "numero": numero,
                "nom": analyse["nom"],
                "cote": cote,
                "cote_source": source,
                "cote_collectee_a": collecte_a,
                "score_m3": score,
                "motif": (
                    "Cote elevee et "
                    "indicateurs favorables"
                ),
            })

        # ----------------------------------------
        # FAVORIS VULNERABLES
        # ----------------------------------------

        if (
            cote <= SEUIL_COTE_FAVORI
            and score < SEUIL_SCORE_FAVORI_FAIBLE
        ):

            resultat["favoris_a_examiner"].append({
                "numero": numero,
                "nom": analyse["nom"],
                "cote": cote,
                "cote_source": source,
                "cote_collectee_a": collecte_a,
                "score_m3": score,
                "motif": (
                    "Cote basse et "
                    "indicateurs faibles"
                ),
            })

    if numeros_analyses != set(chevaux):
        raise RuntimeError(
            "Liste des chevaux analyses incomplete"
        )

    # ========================================================
    # 9. ENRICHISSEMENT DU CLASSEMENT
    # ========================================================

    for cle in (
        "classement",
        "classement_partiel",
    ):

        for position in resultat[cle]:

            numero = position.get("numero")

            if numero not in numeros_analyses:
                raise RuntimeError(
                    "Classement incoherent "
                    "avec les analyses"
                )

            if not verifier_score(
                position.get("score")
            ):
                raise RuntimeError(
                    "Score de classement invalide"
                )

            position["score_m3"] = position["score"]

    # Validation finale apres enrichissement.
    verifier_resultat(resultat)

    return resultat


# ============================================================
# 10. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m3(
    course: Any,
) -> dict:
    """Point d'entree explicite du moteur M3."""

    return analyser_course(course)


# ============================================================
# 11. CLASSE MOTEUR M3
# ============================================================

class MoteurM3:
    """
    Moteur M3 independant.

    Exemple :
        moteur = MoteurM3()
        resultat = moteur.analyser(course)
    """

    nom = MOTEUR
    version = VERSION

    def analyser(
        self,
        course: Any,
    ) -> dict:
        return analyser_course(course)


# ============================================================
# 12. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Execution en lecture seule.

    Commande :
        python -m moteurs.m3 --input course.json

    Codes de sortie :
        0 : analyse complete disponible
        2 : donnees insuffisantes ou course invalide
        1 : erreur technique
    """

    try:
        verifier_noyau()

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
            f"Erreur M3 : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 13. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
