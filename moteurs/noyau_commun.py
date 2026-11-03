#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.3 — Noyau technique commun M1 à M5.

PRINCIPES :
- Courses PMU physiquement disputées en France uniquement.
- Vérification obligatoire de la localisation et du départ.
- Analyse des chevaux à partir d'indicateurs documentés.
- Aucune invention de données manquantes.
- Exclusion des non-partants.
- Cinq positions prédites si cinq chevaux sont admissibles.
- Classement partiel si les données sont insuffisantes.
- Aucune écriture de fichier, publication ou création de FIGÉ.
- Traçabilité des données et des configurations.

Les moteurs M1 à M5 doivent conserver leurs propres
critères, pondérations et décisions sportives.
"""

import argparse
import hashlib
import json
import math
import re
import sys

from datetime import datetime, timezone
from pathlib import Path


VERSION = "2.3"
TAILLE_MAX_OCTETS = 5 * 1024 * 1024

FORMAT_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


# ============================================================
# 1. HORODATAGE
# ============================================================

def maintenant():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 2. VALIDATION DES NOTES
# ============================================================

def note_valide(valeur):
    if isinstance(valeur, bool):
        return None

    if not isinstance(valeur, (int, float)):
        return None

    try:
        nombre = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(nombre):
        return None

    if not 0 <= nombre <= 100:
        return None

    return nombre


# ============================================================
# 3. CONFIGURATION DES MOTEURS
# ============================================================

def verifier_configuration(
    moteur,
    poids,
    champ,
    couverture_min
):
    if not isinstance(moteur, str) or not moteur.strip():
        raise ValueError("Nom du moteur invalide")

    if not isinstance(champ, str) or not champ.strip():
        raise ValueError("Champ d'analyse invalide")

    if not isinstance(poids, dict) or not poids:
        raise ValueError("Ponderations absentes")

    if (
        isinstance(couverture_min, bool)
        or not isinstance(couverture_min, (int, float))
    ):
        raise ValueError("Couverture minimale invalide")

    try:
        couverture_min = float(couverture_min)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Couverture minimale invalide")

    if (
        not math.isfinite(couverture_min)
        or not 0 < couverture_min <= 1
    ):
        raise ValueError(
            "Couverture minimale hors de ]0, 1]"
        )

    coefficients = []

    for critere, coefficient in poids.items():

        if (
            not isinstance(critere, str)
            or not critere.strip()
        ):
            raise ValueError("Nom de critere invalide")

        if (
            isinstance(coefficient, bool)
            or not isinstance(coefficient, (int, float))
        ):
            raise ValueError(
                f"Coefficient invalide : {critere}"
            )

        try:
            coefficient = float(coefficient)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(
                f"Coefficient invalide : {critere}"
            )

        if (
            not math.isfinite(coefficient)
            or coefficient <= 0
        ):
            raise ValueError(
                f"Coefficient non positif : {critere}"
            )

        coefficients.append(coefficient)

    total = math.fsum(coefficients)

    if not math.isfinite(total) or total <= 0:
        raise ValueError(
            "Somme des coefficients invalide"
        )

    return total


# ============================================================
# 4. VALIDATION DES COURSES
# ============================================================

def verifier_course(course):

    if not isinstance(course, dict):
        return False, "Format de course invalide"

    identifiant = course.get("id")

    if (
        isinstance(identifiant, bool)
        or not isinstance(identifiant, (str, int))
        or not str(identifiant).strip()
    ):
        return False, "Identifiant de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    depart = course.get("depart")

    if not isinstance(depart, str) or not depart.strip():
        return False, "Date de depart absente"

    if not FORMAT_DEPART.fullmatch(depart):
        return False, "Format ISO du depart invalide"

    try:
        date = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )

        if date.tzinfo is None or date.utcoffset() is None:
            return False, "Fuseau horaire absent"

        if date <= datetime.now(timezone.utc):
            return False, "Depart deja passe"

    except (ValueError, TypeError, OverflowError):
        return False, "Date de depart invalide"

    partants = course.get("partants")

    if not isinstance(partants, list):
        return False, "Liste des partants absente"

    numeros = set()
    actifs = 0
    non_partants = set()

    for cheval in partants:

        if not isinstance(cheval, dict):
            return False, "Cheval invalide"

        numero = cheval.get("numero")
        nom = cheval.get("nom")
        np = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numero invalide"

        if numero in numeros:
            return False, "Numero en double"

        numeros.add(numero)

        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom invalide"

        if not isinstance(np, bool):
            return False, "Statut non-partant invalide"

        if np:
            non_partants.add(numero)
        else:
            actifs += 1

    if actifs < 5:
        return False, "Moins de cinq partants actifs"

    if "nombre_partants" in course:

        nombre = course["nombre_partants"]

        if type(nombre) is not int or nombre != actifs:
            return False, (
                "Nombre de partants actifs incoherent"
            )

    if "non_partants" in course:

        liste = course["non_partants"]

        if not isinstance(liste, list):
            return False, (
                "Liste des non-partants invalide"
            )

        if any(type(n) is not int for n in liste):
            return False, (
                "Numero de non-partant invalide"
            )

        if len(liste) != len(set(liste)):
            return False, (
                "Non-partants en double"
            )

        if set(liste) != non_partants:
            return False, (
                "Liste des non-partants incoherente"
            )

    return True, "Course verifiee"


# ============================================================
# 5. ANALYSE INDIVIDUELLE DES CHEVAUX
# ============================================================

def analyser_cheval(
    cheval,
    champ,
    poids,
    couverture_min,
    poids_total=None
):

    if poids_total is None:
        poids_total = verifier_configuration(
            "MOTEUR",
            poids,
            champ,
            couverture_min
        )

    donnees = cheval.get(champ)

    if not isinstance(donnees, dict):
        donnees = {}

    details = {}
    contributions = []
    coefficients_disponibles = []

    for critere, coefficient in poids.items():

        valeur = note_valide(
            donnees.get(critere)
        )

        if valeur is None:
            continue

        details[critere] = valeur

        contributions.append(
            valeur * coefficient
        )

        coefficients_disponibles.append(
            coefficient
        )

    poids_disponible = math.fsum(
        coefficients_disponibles
    )

    couverture_brute = (
        poids_disponible / poids_total
        if poids_total > 0 else 0.0
    )

    couverture_brute = min(
        1.0,
        max(0.0, couverture_brute)
    )

    admissible = (
        poids_disponible > 0
        and couverture_brute + 1e-12 >= couverture_min
    )

    score_brut = None
    score = None

    if admissible:

        score_brut = (
            math.fsum(contributions)
            / poids_disponible
        )

        if not math.isfinite(score_brut):
            raise ValueError(
                "Score non fini"
            )

        score = round(score_brut, 2)

    risques = [
        {
            "critere": cle,
            "note": valeur,
            "motif": "Indicateur faible"
        }
        for cle, valeur in details.items()
        if valeur < 40
    ]

    return {
        "numero": cheval["numero"],
        "nom": cheval["nom"],
        "score": score,
        "couverture": round(
            couverture_brute, 4
        ),
        "criteres": details,
        "criteres_manquants": [
            cle for cle in poids
            if cle not in details
        ],
        "risques": risques,
        "admissible": admissible,
        "_score_brut": score_brut,
        "_couverture_brute": couverture_brute
    }


# ============================================================
# 6. EMPREINTE DE CONFIGURATION
# ============================================================

def empreinte_configuration(
    moteur,
    poids,
    champ,
    couverture_min
):

    configuration = {
        "moteur": moteur,
        "poids": poids,
        "champ": champ,
        "couverture_min": couverture_min,
        "version": VERSION
    }

    contenu = json.dumps(
        configuration,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False
    ).encode("utf-8")

    return hashlib.sha256(contenu).hexdigest()


# ============================================================
# 7. ANALYSE COMPLETE D'UNE COURSE
# ============================================================

def analyser_course(
    course,
    moteur,
    poids,
    champ,
    couverture_min=0.60
):

    poids_total = verifier_configuration(
        moteur,
        poids,
        champ,
        couverture_min
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
        "statut": "NON_ANALYSABLE",
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
                couverture_min
            )
        )
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
            poids_total
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

    admissibles = sorted(
        (
            c for c in analyses
            if c["admissible"]
        ),
        key=lambda c: (
            -c["_score_brut"],
            -c["_couverture_brute"],
            c["numero"]
        )
    )

    resultat["chevaux_evalues"] = len(
        admissibles
    )

    classement = [
        {
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            "couverture": cheval["couverture"],
            "risques": cheval["risques"]
        }
        for position, cheval in enumerate(
            admissibles[:5],
            start=1
        )
    ]

    resultat["alertes_risques"] = [
        {
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "risques": cheval["risques"]
        }
        for cheval in analyses
        if cheval["risques"]
    ]

    if len(admissibles) >= 5:

        resultat["classement"] = classement
        resultat["statut"] = "ANALYSE_DISPONIBLE"
        resultat["raison"] = (
            "Cinq positions calculees "
            "sur indicateurs fournis. "
            "Prediction non garantie."
        )

    else:

        resultat["classement_partiel"] = classement
        resultat["statut"] = "DONNEES_INSUFFISANTES"
        resultat["raison"] = (
            "Moins de cinq chevaux suffisamment "
            "documentes. Aucun classement complet."
        )

    return resultat


# ============================================================
# 8. VALIDATION STRICTE DU JSON
# ============================================================

def refuser_doublons(paires):

    resultat = {}

    for cle, valeur in paires:

        if cle in resultat:
            raise ValueError(
                f"Cle JSON dupliquee : {cle}"
            )

        resultat[cle] = valeur

    return resultat


def refuser_constante(valeur):
    raise ValueError(
        f"Constante JSON interdite : {valeur}"
    )


# ============================================================
# 9. EXECUTION SECURISEE
# ============================================================

def executer(analyse):

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2 - Analyse hippique "
            "en lecture seule"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course"
    )

    args = parser.parse_args()

    try:

        chemin = Path(args.input)

        if chemin.stat().st_size > TAILLE_MAX_OCTETS:
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
            parse_constant=refuser_constante
        )

        resultat = analyse(course)

        if (
            not isinstance(resultat, dict)
            or "statut" not in resultat
        ):
            raise ValueError(
                "Resultat d'analyse invalide"
            )

        resultat["source_sha256"] = (
            hashlib.sha256(contenu).hexdigest()
        )

        print(
            json.dumps(
                resultat,
                ensure_ascii=False,
                indent=2,
                allow_nan=False
            )
        )

        return (
            0
            if resultat["statut"] == "ANALYSE_DISPONIBLE"
            else 2
        )

    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        OverflowError,
        KeyError,
        ZeroDivisionError
    ) as erreur:

        print(
            f"Erreur X1000 : {erreur}",
            file=sys.stderr
        )

        return 1
