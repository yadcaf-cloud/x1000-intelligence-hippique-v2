#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — M3 : OUTSIDERS ET FAVORIS VULNERABLES

MISSION
-------
Analyse sportive indépendante des chevaux.

Détecter :
- Les outsiders présentant des indicateurs favorables.
- Les favoris dont les indicateurs sont faibles.
- Cinq positions prédites si les données sont suffisantes.

CRITERES
--------
Forme              : 25 %
Progression         : 25 %
Aptitude parcours   : 20 %
Régularité          : 15 %
Potentiel surprise  : 15 %

SECURITE
--------
- Courses PMU physiquement disputées en France.
- Vérifications techniques déléguées au noyau commun.
- Données sportives documentées.
- Aucune donnée inventée.
- Aucun FIGE automatique ou rétroactif.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucune modification des archives.
- Aucune écriture dans le dépôt.

M3 conserve son indépendance sportive.
"""

from __future__ import annotations

import argparse
import copy
import math
import sys

from datetime import datetime, timezone
from typing import Any


# ============================================================
# 1. IDENTITE ET CONFIGURATION M3
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

STATUTS_ATTENDUS = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})


# ============================================================
# 2. IMPORT CONTROLE DU NOYAU COMMUN
# ============================================================

noyau_commun = None
ERREUR_IMPORT = None

try:
    if __package__:
        from . import noyau_commun
    else:
        import noyau_commun

except ImportError as erreur:
    ERREUR_IMPORT = erreur


# ============================================================
# 3. VALIDATION CONFIGURATION M3
# ============================================================

def verifier_configuration_locale() -> None:
    """Valide les paramètres indépendants de M3."""

    if MOTEUR != "M3":
        raise RuntimeError("Identité M3 invalide")

    if not isinstance(VERSION, str) or not VERSION:
        raise RuntimeError("Version M3 invalide")

    if CHAMP != "indicateurs_m3":
        raise RuntimeError("Champ M3 invalide")

    criteres = {
        "forme",
        "progression",
        "aptitude_parcours",
        "regularite",
        "potentiel_surprise",
    }

    if not isinstance(POIDS, dict):
        raise RuntimeError("Pondérations M3 invalides")

    if set(POIDS) != criteres:
        raise RuntimeError(
            "Les cinq critères M3 sont obligatoires"
        )

    for critere, poids in POIDS.items():

        if type(poids) not in (int, float):
            raise RuntimeError(
                f"Poids non numérique : {critere}"
            )

        if not math.isfinite(poids) or poids <= 0:
            raise RuntimeError(
                f"Poids invalide : {critere}"
            )

    if not math.isclose(
        math.fsum(POIDS.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise RuntimeError(
            "La somme des pondérations doit être égale à 1"
        )

    if (
        type(COUVERTURE_MIN) not in (int, float)
        or not math.isfinite(COUVERTURE_MIN)
        or not 0 < COUVERTURE_MIN <= 1
    ):
        raise RuntimeError(
            "Couverture minimale M3 invalide"
        )

    seuils = (
        SEUIL_COTE_OUTSIDER,
        SEUIL_SCORE_OUTSIDER,
        SEUIL_COTE_FAVORI,
        SEUIL_SCORE_FAVORI_FAIBLE,
    )

    if any(
        type(x) not in (int, float)
        or not math.isfinite(x)
        for x in seuils
    ):
        raise RuntimeError("Seuils M3 invalides")

    if not (
        1 < SEUIL_COTE_FAVORI < SEUIL_COTE_OUTSIDER
    ):
        raise RuntimeError(
            "Seuils de cotes incohérents"
        )

    if not (
        0 <= SEUIL_SCORE_FAVORI_FAIBLE
        < SEUIL_SCORE_OUTSIDER <= 100
    ):
        raise RuntimeError(
            "Seuils de scores incohérents"
        )


# ============================================================
# 4. VALIDATION DU NOYAU COMMUN
# ============================================================

def verifier_noyau() -> None:
    """Vérifie la compatibilité M3 / noyau commun."""

    verifier_configuration_locale()

    if noyau_commun is None:
        raise RuntimeError(
            "Noyau commun indisponible : "
            f"{ERREUR_IMPORT}"
        )

    version = getattr(
        noyau_commun,
        "VERSION",
        None,
    )

    if str(version) != VERSION:
        raise RuntimeError(
            f"Version incompatible : "
            f"M3={VERSION}, noyau={version}"
        )

    if not callable(
        getattr(noyau_commun, "analyser_course", None)
    ):
        raise RuntimeError(
            "Fonction analyser_course indisponible"
        )

    if not callable(
        getattr(noyau_commun, "executer", None)
    ):
        raise RuntimeError(
            "Fonction executer indisponible"
        )

    statuts = getattr(
        noyau_commun,
        "STATUTS_VALIDES",
        None,
    )

    if (
        not isinstance(statuts, (set, frozenset))
        or statuts != STATUTS_ATTENDUS
    ):
        raise RuntimeError(
            "Statuts du noyau incompatibles"
        )


# ============================================================
# 5. VALIDATION DES DATES
# ============================================================

def lire_date(valeur: Any) -> datetime | None:
    """Lit une date ISO avec fuseau horaire explicite."""

    if not isinstance(valeur, str):
        return None

    valeur = valeur.strip()

    if not valeur:
        return None

    try:
        if valeur.endswith("Z"):
            valeur = valeur[:-1] + "+00:00"

        date = datetime.fromisoformat(valeur)

        if date.utcoffset() is None:
            return None

        return date.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


# ============================================================
# 6. VALIDATION DES COTES
# ============================================================

def verifier_cote(
    cheval: dict,
    depart: Any,
) -> tuple[float | None, str | None, str | None]:
    """
    Accepte uniquement une cote :
    - Numérique, finie et supérieure à 1.
    - Avec une source non vide.
    - Horodatée avec fuseau horaire.
    - Antérieure au départ.
    - Non datée dans le futur.

    Une source déclarée ne prouve pas à elle seule
    l'authenticité de la donnée.
    """

    cote = cheval.get("cote")
    source = cheval.get("cote_source")
    collecte_a = cheval.get("cote_collectee_a")

    if type(cote) not in (int, float):
        return None, None, None

    try:
        cote = float(cote)
    except (ValueError, TypeError, OverflowError):
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

    return cote, source.strip(), collecte_a


# ============================================================
# 7. VALIDATION DES SCORES
# ============================================================

def verifier_score(valeur: Any) -> bool:
    """Valide un score numérique entre 0 et 100."""

    if valeur is None:
        return True

    return (
        type(valeur) in (int, float)
        and math.isfinite(valeur)
        and 0 <= valeur <= 100
    )


def verifier_entree(
    entree: Any,
    champ: str,
) -> None:
    """Vérifie une entrée d'analyse ou de classement."""

    if not isinstance(entree, dict):
        raise RuntimeError(
            f"Entrée invalide dans {champ}"
        )

    numero = entree.get("numero")

    if type(numero) is not int or numero <= 0:
        raise RuntimeError(
            f"Numéro invalide dans {champ}"
        )

    if "score" not in entree:
        raise RuntimeError(
            f"Score absent dans {champ}"
        )

    if not verifier_score(entree["score"]):
        raise RuntimeError(
            f"Score invalide dans {champ}"
        )


# ============================================================
# 8. VALIDATION DU RESULTAT COMMUN
# ============================================================

def verifier_resultat(resultat: Any) -> None:
    """Refuse les sorties incohérentes du noyau."""

    if not isinstance(resultat, dict):
        raise RuntimeError(
            "Résultat commun non conforme"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_ATTENDUS:
        raise RuntimeError("Statut M3 invalide")

    if resultat.get("moteur") != MOTEUR:
        raise RuntimeError(
            "Identité du moteur incohérente"
        )

    if resultat.get("fige") is not False:
        raise RuntimeError(
            "FIGÉ interdit dans la sortie M3"
        )

    if resultat.get("publication") is not False:
        raise RuntimeError(
            "Publication interdite dans la sortie M3"
        )

    champs = (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    )

    for champ in champs:

        entrees = resultat.get(champ)

        if not isinstance(entrees, list):
            raise RuntimeError(
                f"Champ invalide : {champ}"
            )

        numeros = set()

        for entree in entrees:

            verifier_entree(entree, champ)

            numero = entree["numero"]

            if numero in numeros:
                raise RuntimeError(
                    f"Doublon dans {champ}"
                )

            numeros.add(numero)

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
                "Classement partiel incohérent"
            )

    elif classement or partiel:
        raise RuntimeError(
            "Classement interdit pour course non analysable"
        )

    numeros_analyses = {
        e["numero"]
        for e in resultat["chevaux_analyses"]
    }

    for champ in ("classement", "classement_partiel"):

        for position_attendue, entree in enumerate(
            resultat[champ],
            start=1,
        ):

            if entree["numero"] not in numeros_analyses:
                raise RuntimeError(
                    "Cheval classé absent des analyses"
                )

            if (
                type(entree.get("position_predite")) is not int
                or entree["position_predite"] != position_attendue
            ):
                raise RuntimeError(
                    "Position prédite incohérente"
                )


# ============================================================
# 9. VALIDATION DES PARTANTS
# ============================================================

def construire_partants(course: Any) -> dict:
    """Construit la liste des partants actifs vérifiés."""

    if not isinstance(course, dict):
        raise RuntimeError("Course M3 invalide")

    partants = course.get("partants")

    if not isinstance(partants, list):
        raise RuntimeError("Partants M3 invalides")

    chevaux = {}
    numeros_tous = set()

    for cheval in partants:

        if not isinstance(cheval, dict):
            raise RuntimeError("Cheval M3 invalide")

        numero = cheval.get("numero")

        if type(numero) is not int or numero <= 0:
            raise RuntimeError(
                "Numéro de cheval invalide"
            )

        if numero in numeros_tous:
            raise RuntimeError(
                "Numéro de cheval en double"
            )

        numeros_tous.add(numero)

        if type(cheval.get("non_partant")) is not bool:
            raise RuntimeError(
                "Statut non-partant invalide"
            )

        if not cheval["non_partant"]:

            nom = cheval.get("nom")

            if not isinstance(nom, str) or not nom.strip():
                raise RuntimeError(
                    "Nom du partant invalide"
                )

            chevaux[numero] = cheval

    return chevaux


# ============================================================
# 10. ANALYSE SPORTIVE INDEPENDANTE M3
# ============================================================

def analyser_course(course: Any) -> dict:
    """
    Analyse M3 sans modifier la course d'origine.

    Le noyau calcule les scores documentés.
    M3 examine ensuite les cotes valides.
    """

    verifier_noyau()

    # Copie de protection des données d'entrée.
    course_locale = copy.deepcopy(course)

    resultat_brut = noyau_commun.analyser_course(
        course=course_locale,
        moteur=MOTEUR,
        poids=POIDS.copy(),
        champ=CHAMP,
        couverture_min=COUVERTURE_MIN,
    )

    verifier_resultat(resultat_brut)

    # Ne jamais modifier le résultat original du noyau.
    resultat = copy.deepcopy(resultat_brut)

    resultat["outsiders_potentiels"] = []
    resultat["favoris_a_examiner"] = []

    if resultat["statut"] == "NON_ANALYSABLE":
        return resultat

    chevaux = construire_partants(course_locale)

    numeros_analyses = set()

    for analyse in resultat["chevaux_analyses"]:

        numero = analyse["numero"]

        if numero not in chevaux:
            raise RuntimeError(
                "Cheval analysé absent des partants actifs"
            )

        if numero in numeros_analyses:
            raise RuntimeError(
                "Cheval analysé plusieurs fois"
            )

        numeros_analyses.add(numero)

        cheval = chevaux[numero]

        nom = analyse.get("nom")

        if (
            not isinstance(nom, str)
            or nom != cheval["nom"]
        ):
            raise RuntimeError(
                "Nom du cheval incohérent"
            )

        cote, source, collecte_a = verifier_cote(
            cheval,
            course_locale.get("depart"),
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
                "Cote invalide ou provenance insuffisante"
            )

        score = analyse["score"]

        if score is None or cote is None:
            continue

        # --------------------------------------------
        # OUTSIDERS POTENTIELS
        # --------------------------------------------

        if (
            cote >= SEUIL_COTE_OUTSIDER
            and score >= SEUIL_SCORE_OUTSIDER
        ):

            resultat["outsiders_potentiels"].append({
                "numero": numero,
                "nom": nom,
                "cote": cote,
                "cote_source": source,
                "cote_collectee_a": collecte_a,
                "score_m3": score,
                "motif": (
                    "Cote élevée et indicateurs favorables"
                ),
            })

        # --------------------------------------------
        # FAVORIS A EXAMINER
        # --------------------------------------------

        if (
            cote <= SEUIL_COTE_FAVORI
            and score < SEUIL_SCORE_FAVORI_FAIBLE
        ):

            resultat["favoris_a_examiner"].append({
                "numero": numero,
                "nom": nom,
                "cote": cote,
                "cote_source": source,
                "cote_collectee_a": collecte_a,
                "score_m3": score,
                "motif": (
                    "Cote basse et indicateurs faibles"
                ),
            })

    if numeros_analyses != set(chevaux):
        raise RuntimeError(
            "Liste des chevaux analysés incomplète"
        )

    # ========================================================
    # 11. ENRICHISSEMENT DU CLASSEMENT
    # ========================================================

    for champ in ("classement", "classement_partiel"):

        for position in resultat[champ]:
            position["score_m3"] = position["score"]

    resultat["outsiders_potentiels"].sort(
        key=lambda x: (-x["score_m3"], -x["cote"], x["numero"])
    )

    resultat["favoris_a_examiner"].sort(
        key=lambda x: (x["score_m3"], x["cote"], x["numero"])
    )

    verifier_resultat(resultat)

    return resultat


# ============================================================
# 12. INTERFACE DU COORDINATEUR X1000
# ============================================================

def analyser_course_m3(course: Any) -> dict:
    """Point d'entrée explicite du moteur M3."""
    return analyser_course(course)


# ============================================================
# 13. CLASSE MOTEUR M3
# ============================================================

class MoteurM3:
    """Moteur sportif indépendant M3."""

    nom = MOTEUR
    version = VERSION
    champ = CHAMP

    def analyser(self, course: Any) -> dict:
        return analyser_course(course)

    def verifier(self) -> bool:
        verifier_noyau()
        return True


# ============================================================
# 14. AUTOTEST SANS COLLECTE PMU
# ============================================================

def self_test() -> int:
    """
    Vérifie la configuration et les interfaces.

    Aucun téléchargement.
    Aucune analyse réelle.
    Aucun FIGÉ.
    Aucune publication.
    Aucune écriture d'archives.
    """

    try:
        verifier_noyau()

        assert MOTEUR == "M3"
        assert VERSION == "2.4"
        assert len(POIDS) == 5
        assert COUVERTURE_MIN == 0.65

        assert verifier_score(0)
        assert verifier_score(100)
        assert not verifier_score(-1)
        assert not verifier_score(101)
        assert not verifier_score(float("nan"))

        assert lire_date(
            "2026-11-04T10:00:00+01:00"
        ) is not None

        assert lire_date(
            "2026-11-04T10:00:00"
        ) is None

        assert callable(analyser_course)
        assert callable(analyser_course_m3)

        moteur = MoteurM3()

        assert moteur.nom == MOTEUR
        assert moteur.verifier() is True

        print("X1000 V2.4 — M3")
        print("AUTOTEST : OK")
        print("Moteur : M3")
        print("Spécialité : outsiders et favoris vulnérables")
        print("Critères indépendants : 5")
        print("Pondérations : 100 %")
        print("Couverture minimale : 65 %")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Modification archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except Exception as erreur:
        print(
            f"AUTOTEST M3 : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )
        return 1


# ============================================================
# 15. EXECUTION SECURISEE
# ============================================================

def main() -> int:
    """
    Commandes :
        python -m moteurs.m3 --self-test
        python -m moteurs.m3 --input course.json

    Le noyau commun gère l'interface d'analyse.
    """

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — M3",
        add_help=False,
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    args, _ = parser.parse_known_args()

    if args.self_test:
        return self_test()

    try:
        verifier_noyau()

        code = noyau_commun.executer(analyser_course)

        if type(code) is not int:
            raise RuntimeError(
                "Code de sortie du noyau invalide"
            )

        return code

    except Exception as erreur:
        print(
            f"ERREUR M3 : {type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )
        return 1


# ============================================================
# 16. POINT D'ENTREE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
