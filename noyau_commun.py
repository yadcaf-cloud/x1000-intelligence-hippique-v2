#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — NOYAU COMMUN M1 A M5

MISSION
-------
Fournir une base technique commune aux cinq moteurs
sportifs indépendants M1, M2, M3, M4 et M5.

FONCTIONS
---------
- Validation structurelle des courses.
- Vérification des départs futurs.
- Contrôle des partants et non-partants.
- Validation des indicateurs sportifs.
- Calcul des scores pondérés.
- Gestion des données insuffisantes.
- Production des cinq positions prédites.
- Conservation des classements partiels.
- Compatibilité des sorties M1 à M5.

SECURITE
--------
- Courses PMU physiquement disputées en France.
- Aucune donnée sportive inventée.
- Aucune collecte PMU.
- Aucune publication automatique.
- Aucun FIGÉ automatique ou rétroactif.
- Aucune validation officielle automatique.
- Aucune écriture dans les archives.
- Aucune modification du dépôt.

IMPORTANT
---------
Les attestations présentes dans les données
ne constituent pas une vérification indépendante.

Le noyau refuse les données structurellement
invalides mais ne certifie pas leur provenance.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# ============================================================
# 1. IDENTITE DU NOYAU
# ============================================================

VERSION = "2.4"

STATUTS_VALIDES = frozenset({
    "ANALYSE_DISPONIBLE",
    "DONNEES_INSUFFISANTES",
    "NON_ANALYSABLE",
})

MOTEURS_VALIDES = frozenset({
    "M1", "M2", "M3", "M4", "M5"
})

FORMAT_COURSE = re.compile(
    r"^\d{4}-\d{2}-\d{2}-R[1-9]\d*-C[1-9]\d*$"
)

COUVERTURE_TOLERANCE = 1e-9


# ============================================================
# 2. VALIDATION DES NOTES SPORTIVES
# ============================================================

def note_valide(valeur: Any) -> float | None:
    """Accepte uniquement une note finie entre 0 et 100."""

    if type(valeur) not in (int, float):
        return None

    try:
        nombre = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(nombre):
        return None

    if not 0 <= nombre <= 100:
        return None

    return nombre


# ============================================================
# 3. VALIDATION DES DATES
# ============================================================

def lire_date(valeur: Any) -> datetime | None:
    """Lit une date ISO avec fuseau horaire obligatoire."""

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
# 4. VALIDATION STRUCTURELLE DES COURSES
# ============================================================

def verifier_course(course: Any) -> tuple[bool, str]:
    """
    Vérifie les données déclarées d'une course.

    Cette vérification est structurelle.
    Elle ne remplace pas le recoupement
    avec une source officielle indépendante.
    """

    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if not isinstance(identifiant, str):
        return False, "Identifiant de course absent"

    if not FORMAT_COURSE.fullmatch(identifiant):
        return False, "Format d'identifiant invalide"

    try:
        date_identifiant = datetime.strptime(
            identifiant[:10], "%Y-%m-%d"
        ).date()
    except ValueError:
        return False, "Date d'identifiant invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non vérifiée"

    if course.get("depart_verifie") is not True:
        return False, "Départ non vérifié"

    depart = lire_date(course.get("depart"))

    if depart is None:
        return False, "Date de départ ou fuseau invalide"

    if depart <= datetime.now(timezone.utc):
        return False, "Départ déjà passé"

    # Comparaison selon le calendrier français.
    from zoneinfo import ZoneInfo

    date_france = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).date()

    if date_identifiant != date_france:
        return False, "Date de course incohérente"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants absente"

    numeros = set()
    actifs = 0

    for cheval in partants:

        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        non_partant = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numéro de cheval invalide"

        if numero in numeros:
            return False, "Numéro de cheval en double"

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom de cheval invalide"

        if type(non_partant) is not bool:
            return False, "Statut non-partant invalide"

        if not non_partant:
            actifs += 1

    if actifs < 5:
        return False, "Moins de cinq partants actifs"

    return True, "Course structurellement valide"


# ============================================================
# 5. VALIDATION DES PARAMETRES MOTEUR
# ============================================================

def verifier_parametres(
    moteur: Any,
    poids: Any,
    champ: Any,
    couverture_min: Any,
) -> tuple[bool, str]:
    """Valide la configuration sportive du moteur."""

    if moteur not in MOTEURS_VALIDES:
        return False, "Moteur inconnu"

    if not isinstance(champ, str) or not champ.strip():
        return False, "Champ d'indicateurs invalide"

    if not isinstance(poids, dict) or not poids:
        return False, "Pondérations absentes"

    for critere, coefficient in poids.items():

        if not isinstance(critere, str) or not critere.strip():
            return False, "Critère sportif invalide"

        if type(coefficient) not in (int, float):
            return False, "Pondération non numérique"

        if not math.isfinite(coefficient) or coefficient <= 0:
            return False, "Pondération invalide"

    if not math.isclose(
        math.fsum(poids.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        return False, "Somme des pondérations différente de 1"

    if type(couverture_min) not in (int, float):
        return False, "Seuil de couverture non numérique"

    if not math.isfinite(couverture_min):
        return False, "Seuil de couverture non fini"

    if not 0 < couverture_min <= 1:
        return False, "Seuil de couverture hors limites"

    return True, "Configuration moteur valide"


# ============================================================
# 6. CONSTRUCTION DU RESULTAT INITIAL
# ============================================================

def nouveau_resultat(
    course: Any,
    moteur: str,
    raison: str,
) -> dict:
    """Crée une sortie uniforme pour les cinq moteurs."""

    return {
        "moteur": moteur,
        "version": VERSION,
        "analyse_a": datetime.now(
            timezone.utc
        ).isoformat(),
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "statut": "NON_ANALYSABLE",
        "raison": raison,
        "chevaux_analyses": [],
        "classement": [],
        "classement_partiel": [],
        "fige": False,
        "publication": False,
    }


# ============================================================
# 7. ANALYSE COMMUNE DES CINQ MOTEURS
# ============================================================

def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> dict:
    """
    Calcule les scores à partir des données fournies.

    Chaque moteur conserve ses propres :
    - Critères.
    - Pondérations.
    - Seuil de couverture.
    - Champ d'indicateurs.

    Le noyau ne décide pas des pondérations.
    """

    resultat = nouveau_resultat(
        course,
        moteur,
        "Analyse non commencée",
    )

    configuration_ok, raison = verifier_parametres(
        moteur,
        poids,
        champ,
        couverture_min,
    )

    if not configuration_ok:
        resultat["raison"] = raison
        return resultat

    course_ok, raison = verifier_course(course)

    if not course_ok:
        resultat["raison"] = raison
        return resultat

    analyses = []

    for cheval in course["partants"]:

        if cheval["non_partant"]:
            continue

        indicateurs = cheval.get(champ)

        if not isinstance(indicateurs, dict):
            indicateurs = {}

        total = 0.0
        couverture = 0.0
        details = {}

        for critere, coefficient in poids.items():

            valeur = note_valide(
                indicateurs.get(critere)
            )

            if valeur is None:
                continue

            total += valeur * coefficient
            couverture += coefficient
            details[critere] = valeur

        couverture = min(
            1.0,
            math.fsum(
                poids[critere]
                for critere in details
            ),
        )

        score = None

        if (
            couverture + COUVERTURE_TOLERANCE
            >= couverture_min
            and couverture > 0
        ):
            score = round(
                math.fsum(
                    details[critere] * poids[critere]
                    for critere in details
                ) / couverture,
                2,
            )

        analyses.append({
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": score,
            "couverture": round(couverture, 6),
            "criteres": details,
            "admissible": score is not None,
        })

    resultat["chevaux_analyses"] = analyses

    admissibles = [
        cheval
        for cheval in analyses
        if cheval["admissible"]
    ]

    admissibles.sort(
        key=lambda cheval: (
            -cheval["score"],
            -cheval["couverture"],
            cheval["numero"],
        )
    )

    # ========================================================
    # 8. CLASSEMENT PARTIEL OU COMPLET
    # ========================================================

    if len(admissibles) < 5:

        resultat["statut"] = "DONNEES_INSUFFISANTES"

        resultat["raison"] = (
            "Moins de cinq chevaux disposent "
            "d'indicateurs sportifs suffisants"
        )

        resultat["classement_partiel"] = [
            {
                "position_predite": position,
                "numero": cheval["numero"],
                "nom": cheval["nom"],
                "score": cheval["score"],
                f"score_{moteur.lower()}": cheval["score"],
                "couverture": cheval["couverture"],
            }
            for position, cheval in enumerate(
                admissibles,
                start=1,
            )
        ]

        return resultat

    resultat["classement"] = [
        {
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            f"score_{moteur.lower()}": cheval["score"],
            "couverture": cheval["couverture"],
        }
        for position, cheval in enumerate(
            admissibles[:5],
            start=1,
        )
    ]

    resultat["statut"] = "ANALYSE_DISPONIBLE"

    resultat["raison"] = (
        "Classement calculé à partir des indicateurs "
        "fournis. Provenance et fiabilité à vérifier "
        "indépendamment."
    )

    return resultat


# ============================================================
# 9. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(fonction_analyse: Callable[[Any], dict]) -> int:
    """
    Interface commune aux cinq moteurs.

    Codes :
    0 : classement disponible
    2 : données insuffisantes ou non analysable
    1 : erreur technique
    """

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — Analyse hippique en lecture seule"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON contenant une course documentée",
    )

    args = parser.parse_args()

    try:
        if not callable(fonction_analyse):
            raise TypeError(
                "Fonction d'analyse invalide"
            )

        with Path(args.input).open(
            "r",
            encoding="utf-8",
        ) as fichier:
            course = json.load(fichier)

        resultat = fonction_analyse(course)

        if not isinstance(resultat, dict):
            raise TypeError(
                "Résultat d'analyse invalide"
            )

        statut = resultat.get("statut")

        if statut not in STATUTS_VALIDES:
            raise ValueError(
                "Statut de résultat inconnu"
            )

        if resultat.get("fige") is not False:
            raise ValueError(
                "FIGÉ interdit"
            )

        if resultat.get("publication") is not False:
            raise ValueError(
                "Publication interdite"
            )

        print(
            json.dumps(
                resultat,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )

        return (
            0
            if statut == "ANALYSE_DISPONIBLE"
            else 2
        )

    except (
        OSError,
        ValueError,
        TypeError,
        OverflowError,
    ) as erreur:

        print(
            f"ERREUR X1000 : "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 10. AUTOTEST DU NOYAU COMMUN
# ============================================================

def self_test() -> int:
    """Teste le noyau sans données PMU réelles."""

    try:
        assert VERSION == "2.4"
        assert len(MOTEURS_VALIDES) == 5
        assert len(STATUTS_VALIDES) == 3

        assert note_valide(0) == 0.0
        assert note_valide(100) == 100.0
        assert note_valide(-1) is None
        assert note_valide(101) is None
        assert note_valide(True) is None
        assert note_valide(float("nan")) is None

        assert lire_date(
            "2026-11-04T10:00:00+01:00"
        ) is not None

        assert lire_date(
            "2026-11-04T10:00:00"
        ) is None

        for moteur in sorted(MOTEURS_VALIDES):

            valide, _ = verifier_parametres(
                moteur=moteur,
                poids={"test": 1.0},
                champ="indicateurs_test",
                couverture_min=0.60,
            )

            assert valide

        print("X1000 V2.4 — NOYAU COMMUN")
        print("AUTOTEST : OK")
        print("Moteurs compatibles : M1 M2 M3 M4 M5")
        print("Statuts : 3")
        print("Classements partiels : activés")
        print("Scores spécifiques : activés")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Modification archives : aucune")
        print("Statut : CONFIGURATION VALIDÉE")

        return 0

    except Exception as erreur:

        print(
            f"AUTOTEST NOYAU : ECHEC — "
            f"{type(erreur).__name__}: {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 11. INTERFACE DU NOYAU
# ============================================================

def main() -> int:
    """Permet de vérifier le noyau sans analyser de course."""

    parser = argparse.ArgumentParser(
        description="X1000 V2.4 — Noyau commun"
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Vérifier le noyau commun",
    )

    args = parser.parse_args()

    if args.self_test:
        return self_test()

    parser.print_help()
    return 0


# ============================================================
# 12. POINT D'ENTREE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
