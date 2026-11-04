#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - M3 : OUTSIDERS ET FAVORIS VULNERABLES

Analyse sportive independante.
Detection des outsiders et favoris a examiner.
Aucune donnee inventee.
Aucun FIGE ni publication.
Archives non modifiees.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from typing import Any

# ============================================================
# 1. NOYAU COMMUN
# ============================================================

if __package__:
    from . import noyau_commun
else:
    import noyau_commun

analyse_commune = noyau_commun.analyser_course
executer = noyau_commun.executer

# ============================================================
# 2. CONFIGURATION M3
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
# 3. VERIFICATION DU NOYAU
# ============================================================

def verifier_noyau() -> None:
    version = getattr(noyau_commun, "VERSION", None)

    if version != VERSION:
        raise RuntimeError(
            f"Noyau incompatible : "
            f"M3={VERSION}, noyau={version}"
        )

    if not callable(analyse_commune):
        raise RuntimeError("Analyse commune indisponible")

    if not callable(executer):
        raise RuntimeError("Execution commune indisponible")

    if not math.isclose(
        sum(POIDS.values()), 1.0, abs_tol=1e-9
    ):
        raise RuntimeError("Ponderations M3 invalides")


# ============================================================
# 4. DATES ET COTES
# ============================================================

def lire_date(valeur: Any) -> datetime | None:
    if not isinstance(valeur, str):
        return None

    try:
        date = datetime.fromisoformat(
            valeur.strip().replace("Z", "+00:00")
        )

        if date.utcoffset() is None:
            return None

        return date.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


def verifier_cote(
    cheval: dict,
    depart: str,
) -> tuple[float | None, str | None, str | None]:

    cote = cheval.get("cote")
    source = cheval.get("cote_source")
    collecte_a = cheval.get("cote_collectee_a")

    if type(cote) not in (int, float):
        return None, None, None

    if not math.isfinite(cote) or cote <= 1:
        return None, None, None

    if not isinstance(source, str) or not source.strip():
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

    # La source doit avoir ete authentifiee
    # par le collecteur en amont.
    return float(cote), source.strip(), collecte_a


# ============================================================
# 5. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(resultat: Any) -> None:
    if not isinstance(resultat, dict):
        raise RuntimeError("Resultat commun non conforme")

    if not isinstance(resultat.get("statut"), str):
        raise RuntimeError("Statut du resultat absent")

    if resultat["statut"] == "NON_ANALYSABLE":
        return

    for cle in (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    ):
        if not isinstance(resultat.get(cle), list):
            raise RuntimeError(
                f"Champ commun invalide : {cle}"
            )

    for cle in (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    ):
        for entree in resultat[cle]:
            if not isinstance(entree, dict):
                raise RuntimeError(
                    f"Entree invalide dans {cle}"
                )

            if "score" not in entree:
                raise RuntimeError(
                    f"Score absent dans {cle}"
                )

            score = entree["score"]

            if score is not None:
                if (
                    type(score) not in (int, float)
                    or not math.isfinite(score)
                ):
                    raise RuntimeError(
                        f"Score invalide dans {cle}"
                    )


# ============================================================
# 6. ANALYSE SPORTIVE M3
# ============================================================

def analyser_course(course: Any) -> dict:
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
        raise RuntimeError("Course invalide")

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise RuntimeError("Partants invalides")

    chevaux = {}

    for cheval in partants:
        if not isinstance(cheval, dict):
            raise RuntimeError("Cheval invalide")

        numero = cheval.get("numero")

        if type(numero) is not int or numero <= 0:
            raise RuntimeError("Numero invalide")

        if numero in chevaux:
            raise RuntimeError("Numero en double")

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
                "Cheval analyse absent des partants actifs"
            )

        if numero in numeros_analyses:
            raise RuntimeError(
                "Cheval analyse plusieurs fois"
            )

        numeros_analyses.add(numero)
        cheval = chevaux[numero]

        if not isinstance(analyse.get("nom"), str):
            raise RuntimeError("Nom analyse invalide")

        cote, source, collecte_a = verifier_cote(
            cheval,
            course.get("depart"),
        )

        analyse["cote"] = cote
        analyse["cote_source"] = source
        analyse["cote_collectee_a"] = collecte_a
        analyse["score_m3"] = analyse["score"]

        if cote is None and cheval.get("cote") is not None:
            analyse["cote_ignoree"] = (
                "Cote invalide ou provenance insuffisante"
            )

        score = analyse["score"]

        if score is None or cote is None:
            continue

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
                    "Cote elevee et indicateurs favorables"
                ),
            })

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
                    "Cote basse et indicateurs faibles"
                ),
            })

    for cle in ("classement", "classement_partiel"):
        for position in resultat[cle]:
            if position.get("numero") not in numeros_analyses:
                raise RuntimeError(
                    "Classement incoherent avec les analyses"
                )

            position["score_m3"] = position["score"]

    return resultat


# ============================================================
# 7. INTERFACE COORDINATEUR
# ============================================================

def analyser_course_m3(course: Any) -> dict:
    return analyser_course(course)


class MoteurM3:
    nom = MOTEUR
    version = VERSION

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)


# ============================================================
# 8. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    try:
        verifier_noyau()
        return executer(analyser_course)

    except (RuntimeError, ValueError, TypeError) as erreur:
        print(f"Erreur M3 : {erreur}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
