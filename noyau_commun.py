#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 — NOYAU TECHNIQUE COMMUN SECURISE

Validation des courses PMU en France.
Calcul de scores sur indicateurs fournis.
Classements complets ou partiels.
Verification des sorties M1 a M5.

Aucune collecte PMU.
Aucune donnee sportive inventee.
Aucun FIGE automatique ou retroactif.
Aucune publication.
Aucune modification des archives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# ============================================================
# 1. CONFIGURATION
# ============================================================

VERSION = "2.4"

TAILLE_MAX_OCTETS = 5 * 1024 * 1024
MIN_PARTANTS = 5
SEUIL_RISQUE = 40.0

STATUT_DISPONIBLE = "ANALYSE_DISPONIBLE"
STATUT_INSUFFISANT = "DONNEES_INSUFFISANTES"
STATUT_NON_ANALYSABLE = "NON_ANALYSABLE"

STATUTS_VALIDES = frozenset({
    STATUT_DISPONIBLE,
    STATUT_INSUFFISANT,
    STATUT_NON_ANALYSABLE,
})

FORMAT_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


# ============================================================
# 2. HORODATAGE ET NOTES
# ============================================================

def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


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
# 3. CONFIGURATION DES MOTEURS
# ============================================================

def verifier_configuration(
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float,
) -> float:

    if (
        not isinstance(moteur, str)
        or not re.fullmatch(r"M[1-5]", moteur)
    ):
        raise ValueError(
            "Identité de moteur invalide"
        )

    if (
        not isinstance(champ, str)
        or champ != f"indicateurs_{moteur.lower()}"
    ):
        raise ValueError(
            "Champ d'analyse incohérent"
        )

    if not isinstance(poids, dict) or not poids:
        raise ValueError(
            "Pondérations absentes"
        )

    couverture = nombre_fini(couverture_min)

    if couverture is None or not 0 < couverture <= 1:
        raise ValueError(
            "Couverture minimale invalide"
        )

    coefficients = []

    for critere, valeur in poids.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise ValueError(
                "Critère invalide"
            )

        coefficient = nombre_fini(valeur)

        if (
            coefficient is None
            or coefficient <= 0
            or coefficient > 1
        ):
            raise ValueError(
                f"Poids invalide : {critere}"
            )

        coefficients.append(coefficient)

    total = math.fsum(coefficients)

    if not math.isclose(
        total,
        1.0,
        rel_tol=0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "Les pondérations doivent totaliser 1"
        )

    return total


# ============================================================
# 4. VALIDATION DES COURSES
# ============================================================

def verifier_course(
    course: Any,
) -> tuple[bool, str]:

    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        type(identifiant) not in (str, int)
        or not str(identifiant).strip()
    ):
        return False, "Identifiant invalide"

    if course.get(
        "localisation_france_verifiee"
    ) is not True:
        return False, "Localisation France non vérifiée"

    if course.get("depart_verifie") is not True:
        return False, "Départ non vérifié"

    depart = course.get("depart")

    if (
        not isinstance(depart, str)
        or not FORMAT_DEPART.fullmatch(depart)
    ):
        return False, "Format ISO du départ invalide"

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )

        if date_depart.utcoffset() is None:
            return False, "Fuseau horaire absent"

        if date_depart <= datetime.now(timezone.utc):
            return False, "Départ déjà passé"

    except (ValueError, TypeError, OverflowError):
        return False, "Date de départ invalide"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants absente"

    numeros = set()
    non_partants = set()
    actifs = 0

    for cheval in partants:

        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        np = cheval.get("non_partant")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in numeros
        ):
            return False, (
                "Numéro de cheval invalide ou en double"
            )

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom de cheval invalide"

        if type(np) is not bool:
            return False, "Statut non-partant invalide"

        if np:
            non_partants.add(numero)
        else:
            actifs += 1

    if actifs < MIN_PARTANTS:
        return False, "Moins de cinq partants actifs"

    if "nombre_partants" in course:

        nombre = course["nombre_partants"]

        if (
            type(nombre) is not int
            or nombre != actifs
        ):
            return False, (
                "Nombre de partants actifs incohérent"
            )

    if "non_partants" in course:

        liste = course["non_partants"]

        if not isinstance(liste, list):
            return False, (
                "Liste des non-partants invalide"
            )

        if any(type(n) is not int for n in liste):
            return False, (
                "Numéro de non-partant invalide"
            )

        if len(liste) != len(set(liste)):
            return False, "Non-partants en double"

        if set(liste) != non_partants:
            return False, (
                "Liste des non-partants incohérente"
            )

    return True, "Course vérifiée"


# ============================================================
# 5. EMPREINTE SHA-256
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
        "noyau": VERSION,
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
# 6. ANALYSE INDIVIDUELLE
# ============================================================

def analyser_cheval(
    cheval: dict,
    champ: str,
    poids: dict,
    couverture_min: float,
    total_poids: float | None = None,
) -> dict:

    if total_poids is None:

        moteur = champ.removeprefix(
            "indicateurs_"
        ).upper()

        total_poids = verifier_configuration(
            moteur,
            poids,
            champ,
            couverture_min,
        )

    donnees = cheval.get(champ)

    if not isinstance(donnees, dict):
        donnees = {}

    criteres = {}
    coefficients = []
    contributions = []

    for critere, coefficient in poids.items():

        note = note_valide(
            donnees.get(critere)
        )

        if note is None:
            continue

        fraction = coefficient / total_poids

        criteres[critere] = note
        coefficients.append(fraction)

        contributions.append(
            note * fraction
        )

    couverture = min(
        1.0,
        max(0.0, math.fsum(coefficients)),
    )

    admissible = (
        couverture > 0
        and couverture + 1e-12 >= couverture_min
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
        "couverture": round(couverture, 4),
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
# 7. VALIDATION DES SORTIES M1 A M5
# ============================================================

def verifier_sortie_analyse(
    resultat: Any,
    course: Any = None,
) -> None:
    """
    Vérifie les sorties des moteurs.

    Empêche :
    - Les doublons.
    - Les classements incohérents.
    - Les scores invalides.
    - Les non-partants classés.
    - Les FIGES et publications.
    """

    if not isinstance(resultat, dict):
        raise ValueError(
            "Sortie d'analyse invalide"
        )

    moteur = resultat.get("moteur")

    if (
        not isinstance(moteur, str)
        or not re.fullmatch(r"M[1-5]", moteur)
    ):
        raise ValueError(
            "Moteur de sortie invalide"
        )

    statut = resultat.get("statut")

    if statut not in STATUTS_VALIDES:
        raise ValueError(
            "Statut de sortie invalide"
        )

    if (
        resultat.get("fige") is not False
        or resultat.get("publication") is not False
    ):
        raise ValueError(
            "FIGE ou publication interdits"
        )

    champs = (
        "chevaux_analyses",
        "classement",
        "classement_partiel",
    )

    for champ in champs:

        if not isinstance(resultat.get(champ), list):
            raise ValueError(
                f"Liste de sortie invalide : {champ}"
            )

    analyses = {}

    for entree in resultat["chevaux_analyses"]:

        if not isinstance(entree, dict):
            raise ValueError(
                "Analyse de cheval invalide"
            )

        numero = entree.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in analyses
        ):
            raise ValueError(
                "Numéro analysé invalide ou en double"
            )

        score = entree.get("score")

        if score is not None:
            if note_valide(score) is None:
                raise ValueError(
                    "Score analysé invalide"
                )

        analyses[numero] = entree

    classement = resultat["classement"]
    partiel = resultat["classement_partiel"]

    if statut == STATUT_DISPONIBLE:

        if len(classement) != 5 or partiel:
            raise ValueError(
                "Cinq positions obligatoires"
            )

    elif statut == STATUT_INSUFFISANT:

        if classement or len(partiel) >= 5:
            raise ValueError(
                "Classement partiel incohérent"
            )

    elif classement or partiel:

        raise ValueError(
            "Classement interdit"
        )

    for positions in (classement, partiel):

        deja = set()

        for rang, entree in enumerate(
            positions,
            start=1,
        ):

            if not isinstance(entree, dict):
                raise ValueError(
                    "Position invalide"
                )

            numero = entree.get("numero")

            if (
                type(numero) is not int
                or numero not in analyses
                or numero in deja
            ):
                raise ValueError(
                    "Numéro classé invalide"
                )

            deja.add(numero)

            if (
                type(entree.get("position_predite"))
                is not int
                or entree["position_predite"] != rang
            ):
                raise ValueError(
                    "Rang incohérent"
                )

            score = note_valide(
                entree.get("score")
            )

            if (
                score is None
                or score != analyses[numero].get("score")
            ):
                raise ValueError(
                    "Score classé incohérent"
                )

    # Vérification supplémentaire des partants.
    if course is not None:

        if (
            not isinstance(course, dict)
            or not isinstance(
                course.get("partants"),
                list,
            )
        ):
            raise ValueError(
                "Course de contrôle invalide"
            )

        actifs = {
            cheval["numero"]: cheval
            for cheval in course["partants"]
            if (
                isinstance(cheval, dict)
                and type(cheval.get("numero")) is int
                and cheval.get("non_partant") is False
            )
        }

        if not set(analyses).issubset(actifs):
            raise ValueError(
                "Non-partant ou cheval inconnu"
            )

        for numero, entree in analyses.items():

            if entree.get("nom") != actifs[
                numero
            ].get("nom"):
                raise ValueError(
                    "Nom de cheval incohérent"
                )

        if (
            statut != STATUT_NON_ANALYSABLE
            and set(analyses) != set(actifs)
        ):
            raise ValueError(
                "Analyses des partants incomplètes"
            )


# ============================================================
# 8. ANALYSE COMPLETE DE COURSE
# ============================================================

def analyser_course(
    course: Any,
    moteur: str,
    poids: dict,
    champ: str,
    couverture_min: float = 0.60,
) -> dict:

    total = verifier_configuration(
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
        "configuration_sha256": (
            empreinte_configuration(
                moteur,
                poids,
                champ,
                couverture_min,
            )
        ),
    }

    if not valide:
        verifier_sortie_analyse(resultat)
        return resultat

    analyses = [
        analyser_cheval(
            cheval,
            champ,
            poids,
            couverture_min,
            total,
        )
        for cheval in course["partants"]
        if not cheval["non_partant"]
    ]

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
            "numero": analyse["numero"],
            "nom": analyse["nom"],
            "risques": analyse["risques"],
        }
        for analyse in analyses
        if analyse["risques"]
    ]

    admissibles = sorted(
        (
            analyse
            for analyse in analyses
            if analyse["admissible"]
        ),
        key=lambda analyse: (
            -analyse["_score_brut"],
            -analyse["_couverture_brute"],
            analyse["numero"],
        ),
    )

    resultat["chevaux_evalues"] = len(admissibles)

    positions = [
        {
            "position_predite": rang,
            "numero": analyse["numero"],
            "nom": analyse["nom"],
            "score": analyse["score"],
            "couverture": analyse["couverture"],
            "risques": analyse["risques"],
        }
        for rang, analyse in enumerate(
            admissibles[:5],
            start=1,
        )
    ]

    if len(admissibles) >= 5:

        resultat["classement"] = positions
        resultat["statut"] = STATUT_DISPONIBLE

        resultat["raison"] = (
            "Cinq positions calculées sur "
            "indicateurs fournis ; "
            "prédiction non garantie"
        )

    else:

        resultat["classement_partiel"] = positions
        resultat["statut"] = STATUT_INSUFFISANT

        resultat["raison"] = (
            "Moins de cinq chevaux admissibles ; "
            "classement partiel conservé"
        )

    verifier_sortie_analyse(resultat, course)

    return resultat


# ============================================================
# 9. SECURITE JSON
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

    with Path(chemin).open("rb") as fichier:

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
# 10. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    analyse: Callable[[Any], dict],
) -> int:

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 — Analyse en lecture seule"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course vérifiée",
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
            resultat,
            course if verifier_course(course)[0] else None,
        )

        # Ne pas modifier le résultat original.
        resultat = dict(resultat)

        resultat["source_sha256"] = empreinte

        print(
            json.dumps(
                resultat,
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
            f"Erreur X1000 : {erreur}",
            file=sys.stderr,
        )

        return 1
