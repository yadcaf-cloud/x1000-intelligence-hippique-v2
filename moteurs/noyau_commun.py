#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — NOYAU TECHNIQUE COMMUN SECURISE

Compatible avec M1, M2, M3, M4 et M5.

FONCTIONS
---------
- Validation structurelle des courses PMU en France.
- Vérification des départs futurs.
- Contrôle des partants et non-partants.
- Calcul des scores sur indicateurs fournis.
- Classements complets ou partiels.
- Détection des indicateurs faibles.
- Lecture stricte des fichiers JSON.
- Traçabilité SHA-256.
- Exécution en lecture seule.
- Autotest sans données PMU réelles.

SECURITE
--------
Aucune collecte PMU.
Aucune donnée sportive inventée.
Aucun FIGÉ automatique ou rétroactif.
Aucune publication automatique.
Aucune modification des archives.

IMPORTANT
---------
Les attestations présentes dans les données
ne constituent pas une validation officielle
ou une vérification indépendante des sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


# ============================================================
# 1. CONSTANTES
# ============================================================

VERSION = "2.4"

TAILLE_MAX_OCTETS = 5 * 1024 * 1024
MIN_PARTANTS = 5
SEUIL_RISQUE = 40.0

MAX_AVANCE_DEPART = timedelta(days=30)

STATUT_DISPONIBLE = "ANALYSE_DISPONIBLE"
STATUT_INSUFFISANT = "DONNEES_INSUFFISANTES"
STATUT_NON_ANALYSABLE = "NON_ANALYSABLE"

STATUTS_VALIDES = frozenset({
    STATUT_DISPONIBLE,
    STATUT_INSUFFISANT,
    STATUT_NON_ANALYSABLE,
})

MOTEURS_VALIDES = frozenset({
    "M1", "M2", "M3", "M4", "M5",
})

FORMAT_ID = re.compile(
    r"^\d{4}-\d{2}-\d{2}-R[1-9]\d*-C[1-9]\d*$"
)

FORMAT_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)

TOLERANCE = 1e-9


# ============================================================
# 2. HORODATAGE
# ============================================================

def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 3. VALIDATION NUMERIQUE
# ============================================================

def nombre_fini(valeur: Any) -> float | None:

    if type(valeur) not in (int, float):
        return None

    try:
        nombre = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(nombre):
        return None

    return nombre


def note_valide(valeur: Any) -> float | None:

    nombre = nombre_fini(valeur)

    if nombre is None:
        return None

    if not 0 <= nombre <= 100:
        return None

    return nombre


# ============================================================
# 4. VALIDATION DES DATES
# ============================================================

def lire_date(valeur: Any) -> datetime | None:

    if not isinstance(valeur, str):
        return None

    if not FORMAT_DEPART.fullmatch(valeur):
        return None

    try:
        date = datetime.fromisoformat(
            valeur.replace("Z", "+00:00")
        )

        if date.utcoffset() is None:
            return None

        return date.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


# ============================================================
# 5. VALIDATION CONFIGURATION
# ============================================================

def verifier_configuration(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> float:

    if moteur not in MOTEURS_VALIDES:
        raise ValueError("Moteur inconnu")

    if not isinstance(champ, str) or not champ.strip():
        raise ValueError("Champ d'analyse invalide")

    if not isinstance(poids, dict) or not poids:
        raise ValueError("Pondérations absentes")

    couverture = nombre_fini(couverture_min)

    if couverture is None or not 0 < couverture <= 1:
        raise ValueError("Couverture minimale invalide")

    coefficients = []

    for critere, valeur in poids.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise ValueError("Nom de critère invalide")

        coefficient = nombre_fini(valeur)

        if coefficient is None or coefficient <= 0:
            raise ValueError(
                f"Coefficient invalide : {critere}"
            )

        coefficients.append(coefficient)

    total = math.fsum(coefficients)

    if not math.isfinite(total) or total <= 0:
        raise ValueError(
            "Somme des coefficients invalide"
        )

    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "La somme des pondérations doit être 1"
        )

    return total


# ============================================================
# 6. VALIDATION STRUCTURELLE DE LA COURSE
# ============================================================

def verifier_course(
    course: Any,
) -> tuple[bool, str]:

    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        not isinstance(identifiant, str)
        or not FORMAT_ID.fullmatch(identifiant)
    ):
        return False, "Identifiant de course invalide"

    try:
        date_id = datetime.strptime(
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
        return False, "Date de départ invalide"

    avance = depart - datetime.now(timezone.utc)

    if avance <= timedelta(0):
        return False, "Départ déjà passé"

    if avance > MAX_AVANCE_DEPART:
        return False, "Départ trop éloigné"

    date_france = depart.astimezone(
        ZoneInfo("Europe/Paris")
    ).date()

    if date_id != date_france:
        return False, "Date de course incohérente"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Partants absents"

    numeros = set()
    non_partants = set()
    actifs = 0

    for cheval in partants:

        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        non_partant = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numéro invalide"

        if numero in numeros:
            return False, "Numéro en double"

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom de cheval invalide"

        if type(non_partant) is not bool:
            return False, "Statut non-partant invalide"

        if non_partant:
            non_partants.add(numero)
        else:
            actifs += 1

    if actifs < MIN_PARTANTS:
        return False, "Moins de cinq partants actifs"

    if "nombre_partants" in course:

        nombre = course["nombre_partants"]

        if type(nombre) is not int or nombre != actifs:
            return False, "Nombre de partants incohérent"

    if "non_partants" in course:

        liste = course["non_partants"]

        if not isinstance(liste, list):
            return False, "Liste des non-partants invalide"

        if any(
            type(numero) is not int or numero <= 0
            for numero in liste
        ):
            return False, "Numéro non-partant invalide"

        if len(liste) != len(set(liste)):
            return False, "Non-partants en double"

        if set(liste) != non_partants:
            return False, "Non-partants incohérents"

    return True, "Course structurellement valide"


# ============================================================
# 7. EMPREINTE SHA-256
# ============================================================

def empreinte_configuration(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> str:

    configuration = {
        "moteur": moteur,
        "poids": poids,
        "champ": champ,
        "couverture_min": couverture_min,
        "version_noyau": VERSION,
    }

    contenu = json.dumps(
        configuration,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


# ============================================================
# 8. ANALYSE INDIVIDUELLE
# ============================================================

def analyser_cheval(
    cheval: dict,
    champ: str,
    poids: dict,
    couverture_min: float,
    total_poids: float | None = None,
) -> dict:

    if total_poids is None:
        total_poids = math.fsum(poids.values())

    donnees = cheval.get(champ)

    if not isinstance(donnees, dict):
        donnees = {}

    criteres = {}
    contributions = []
    coefficients = []

    for critere, coefficient in poids.items():

        note = note_valide(
            donnees.get(critere)
        )

        if note is None:
            continue

        coefficient_normalise = (
            coefficient / total_poids
        )

        criteres[critere] = note
        coefficients.append(coefficient_normalise)

        contributions.append(
            note * coefficient_normalise
        )

    couverture = math.fsum(coefficients)

    couverture = min(
        1.0,
        max(0.0, couverture),
    )

    admissible = (
        couverture > 0
        and couverture + TOLERANCE >= couverture_min
    )

    score_brut = None

    if admissible:

        score_brut = (
            math.fsum(contributions) / couverture
        )

        if not math.isfinite(score_brut):
            raise ValueError("Score non fini")

        score_brut = min(
            100.0,
            max(0.0, score_brut),
        )

    risques = [
        {
            "critere": critere,
            "note": note,
            "motif": "Indicateur faible",
        }
        for critere, note in criteres.items()
        if note < SEUIL_RISQUE
    ]

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": (
            round(score_brut, 2)
            if score_brut is not None
            else None
        ),
        "couverture": round(couverture, 6),
        "criteres": criteres,
        "criteres_manquants": [
            critere
            for critere in poids
            if critere not in criteres
        ],
        "risques": risques,
        "admissible": admissible,
        "_score_brut": score_brut,
        "_couverture_brute": couverture,
    }


# ============================================================
# 9. ANALYSE COMMUNE M1 A M5
# ============================================================

def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float = 0.60,
) -> dict:

    total_poids = verifier_configuration(
        moteur,
        poids,
        champ,
        couverture_min,
    )

    valide, raison = verifier_course(course)

    resultat = {
        "moteur": moteur,
        "version": VERSION,
        "course_id": (
            course.get("id")
            if isinstance(course, dict)
            else None
        ),
        "analyse_a": maintenant(),
        "statut": STATUT_NON_ANALYSABLE,
        "raison": raison,
        "classement": [],
        "classement_partiel": [],
        "chevaux_analyses": [],
        "chevaux_evalues": 0,
        "alertes_risques": [],
        "outsiders_potentiels": [],
        "favoris_a_examiner": [],
        "fige": False,
        "publication": False,
        "configuration_sha256": empreinte_configuration(
            moteur,
            poids,
            champ,
            couverture_min,
        ),
    }

    if not valide:
        return resultat

    analyses = []

    for cheval in course["partants"]:

        if cheval["non_partant"]:
            continue

        analyse = analyser_cheval(
            cheval,
            champ,
            poids,
            couverture_min,
            total_poids,
        )

        analyses.append(analyse)

    resultat["chevaux_analyses"] = [
        {
            cle: valeur
            for cle, valeur in analyse.items()
            if not cle.startswith("_")
        }
        for analyse in analyses
    ]

    resultat["alertes_risques"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "risques": cheval["risques"],
        }
        for cheval in analyses
        if cheval["risques"]
    ]

    admissibles = sorted(
        (
            cheval
            for cheval in analyses
            if cheval["admissible"]
        ),
        key=lambda cheval: (
            -cheval["_score_brut"],
            -cheval["_couverture_brute"],
            cheval["numero"],
        ),
    )

    resultat["chevaux_evalues"] = len(admissibles)

    positions = []

    for position, cheval in enumerate(
        admissibles[:5],
        start=1,
    ):

        score = cheval["score"]

        positions.append({
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": score,
            f"score_{moteur.lower()}": score,
            "couverture": cheval["couverture"],
            "risques": cheval["risques"],
        })

    if len(admissibles) >= 5:

        resultat["classement"] = positions
        resultat["statut"] = STATUT_DISPONIBLE

        resultat["raison"] = (
            "Cinq positions calculées sur les "
            "indicateurs fournis. "
            "Prédiction non garantie."
        )

    else:

        resultat["classement_partiel"] = positions
        resultat["statut"] = STATUT_INSUFFISANT

        resultat["raison"] = (
            "Moins de cinq chevaux admissibles. "
            "Classement partiel conservé."
        )

    return resultat


# ============================================================
# 10. SECURITE JSON
# ============================================================

def refuser_doublons(paires: list) -> dict:

    resultat = {}

    for cle, valeur in paires:

        if cle in resultat:
            raise ValueError(
                f"Clé JSON dupliquée : {cle}"
            )

        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur: str) -> None:

    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


def charger_json_securise(
    chemin: Path,
) -> tuple[Any, str]:

    chemin = Path(chemin)

    taille = chemin.stat().st_size

    if taille > TAILLE_MAX_OCTETS:
        raise ValueError(
            "Fichier JSON trop volumineux"
        )

    with chemin.open("rb") as fichier:

        contenu = fichier.read(
            TAILLE_MAX_OCTETS + 1
        )

    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValueError(
            "Fichier JSON trop volumineux"
        )

    course = json.loads(
        contenu.decode("utf-8"),
        object_pairs_hook=refuser_doublons,
        parse_constant=refuser_constante,
    )

    empreinte = hashlib.sha256(
        contenu
    ).hexdigest()

    return course, empreinte


# ============================================================
# 11. VALIDATION DES SORTIES
# ============================================================

def verifier_sortie_analyse(
    course: Any,
    resultat: dict,
) -> None:

    if not isinstance(resultat, dict):
        raise ValueError(
            "Résultat d'analyse invalide"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_VALIDES:
        raise ValueError(
            "Statut d'analyse invalide"
        )

    if resultat.get("fige") is not False:
        raise ValueError(
            "FIGÉ interdit"
        )

    if resultat.get("publication") is not False:
        raise ValueError(
            "Publication interdite"
        )

    if (
        not isinstance(course, dict)
        or resultat.get("course_id") != course.get("id")
    ):
        raise ValueError(
            "Identifiant de course incohérent"
        )

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if (
        not isinstance(classement, list)
        or not isinstance(partiel, list)
    ):
        raise ValueError(
            "Classements invalides"
        )

    if statut == STATUT_DISPONIBLE:

        if len(classement) != 5 or partiel:
            raise ValueError(
                "Cinq positions complètes requises"
            )

    elif statut == STATUT_INSUFFISANT:

        if classement or len(partiel) >= 5:
            raise ValueError(
                "Classement partiel incohérent"
            )

    elif classement or partiel:
        raise ValueError(
            "Classement interdit pour course non analysable"
        )

    actifs = {
        cheval["numero"]
        for cheval in course.get("partants", [])
        if isinstance(cheval, dict)
        and type(cheval.get("numero")) is int
        and cheval.get("non_partant") is False
    }

    positions = (
        classement
        if statut == STATUT_DISPONIBLE
        else partiel
    )

    numeros = set()

    for rang, ligne in enumerate(
        positions,
        start=1,
    ):

        if not isinstance(ligne, dict):
            raise ValueError(
                "Ligne de classement invalide"
            )

        numero = ligne.get("numero")

        if (
            type(numero) is not int
            or numero not in actifs
            or numero in numeros
        ):
            raise ValueError(
                "Cheval classé invalide ou non-partant"
            )

        numeros.add(numero)

        if (
            type(ligne.get("position_predite")) is not int
            or ligne["position_predite"] != rang
        ):
            raise ValueError(
                "Position prédite invalide"
            )

        if note_valide(ligne.get("score")) is None:
            raise ValueError(
                "Score de classement invalide"
            )

    if statut != STATUT_NON_ANALYSABLE:

        valide, raison = verifier_course(course)

        if not valide:
            raise ValueError(
                f"Course non analysable : {raison}"
            )


# ============================================================
# 12. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    analyse: Callable[[Any], dict],
) -> int:

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 — Analyse hippique "
            "en lecture seule"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course documentée",
    )

    args = parser.parse_args()

    try:

        if not callable(analyse):
            raise ValueError(
                "Fonction d'analyse invalide"
            )

        course, empreinte = charger_json_securise(
            Path(args.input)
        )

        resultat = analyse(course)

        verifier_sortie_analyse(
            course,
            resultat,
        )

        sortie = dict(resultat)
        sortie["source_sha256"] = empreinte

        print(
            json.dumps(
                sortie,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )

        if resultat["statut"] == STATUT_DISPONIBLE:
            return 0

        return 2

    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        OverflowError,
        KeyError,
        ZeroDivisionError,
        RuntimeError,
    ) as erreur:

        print(
            f"ERREUR X1000 : {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 13. AUTOTEST DU NOYAU
# ============================================================

def self_test() -> int:

    try:

        if VERSION != "2.4":
            raise RuntimeError(
                "Version incorrecte"
            )

        if len(MOTEURS_VALIDES) != 5:
            raise RuntimeError(
                "Nombre de moteurs incorrect"
            )

        if note_valide(0) != 0.0:
            raise RuntimeError(
                "Validation note zéro incorrecte"
            )

        if note_valide(100) != 100.0:
            raise RuntimeError(
                "Validation note maximale incorrecte"
            )

        if note_valide(-1) is not None:
            raise RuntimeError(
                "Note négative acceptée"
            )

        if note_valide(101) is not None:
            raise RuntimeError(
                "Note supérieure à 100 acceptée"
            )

        if note_valide(True) is not None:
            raise RuntimeError(
                "Booléen accepté comme note"
            )

        if lire_date(
            "2026-11-04T10:00:00+01:00"
        ) is None:
            raise RuntimeError(
                "Date valide rejetée"
            )

        if lire_date(
            "2026-11-04T10:00:00"
        ) is not None:
            raise RuntimeError(
                "Date sans fuseau acceptée"
            )

        for moteur in MOTEURS_VALIDES:

            verifier_configuration(
                moteur=moteur,
                poids={"test": 1.0},
                champ="indicateurs_test",
                couverture_min=0.60,
            )

        print("X1000 V2.4 — NOYAU COMMUN")
        print("SELF-TEST : OK")
        print("Moteurs : M1 M2 M3 M4 M5")
        print("Classements partiels : activés")
        print("Contrôle JSON : activé")
        print("SHA-256 : activé")
        print("Collecte PMU : aucune")
        print("Publication : aucune")
        print("FIGÉ automatique : aucun")
        print("Écriture archives : aucune")

        return 0

    except Exception as erreur:

        print(
            f"SELF-TEST : ECHEC — {erreur}",
            file=sys.stderr,
        )

        return 1


# ============================================================
# 14. INTERFACE DU NOYAU
# ============================================================

def main() -> int:

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
# 15. DEMARRAGE
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
