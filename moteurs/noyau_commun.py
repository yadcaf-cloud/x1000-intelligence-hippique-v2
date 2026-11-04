#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 V2.4 - NOYAU TECHNIQUE COMMUN SECURISE

Interfaces M1 a M5.
Validation des courses et des sorties.
Analyses sportives en lecture seule.

Aucune collecte PMU automatique.
Aucune donnee sportive inventee.
Aucun FIGE automatique ou retroactif.
Aucune publication automatique.
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


VERSION = "2.4"

TAILLE_MAX_OCTETS = 5 * 1024 * 1024
MIN_PARTANTS = 5
SEUIL_RISQUE = 40.0

STATUT_DISPONIBLE = "ANALYSE_DISPONIBLE"
STATUT_INSUFFISANT = "DONNEES_INSUFFISANTES"
STATUT_NON_ANALYSABLE = "NON_ANALYSABLE"

STATUTS_VALIDES = {
    STATUT_DISPONIBLE,
    STATUT_INSUFFISANT,
    STATUT_NON_ANALYSABLE,
}

FORMAT_DEPART = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?"
    r"(?:Z|[+-]\d{2}:\d{2})$"
)


# ============================================================
# 1. HORODATAGE
# ============================================================

def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# 2. VALIDATION NUMERIQUE
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

    if nombre is None or not 0 <= nombre <= 100:
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

    if not isinstance(moteur, str) or not moteur.strip():
        raise ValueError("Nom de moteur invalide")

    if not isinstance(champ, str) or not champ.strip():
        raise ValueError("Champ d'analyse invalide")

    if not isinstance(poids, dict) or not poids:
        raise ValueError("Ponderations absentes")

    couverture = nombre_fini(couverture_min)

    if couverture is None or not 0 < couverture <= 1:
        raise ValueError("Couverture minimale invalide")

    coefficients = []

    for critere, valeur in poids.items():
        if not isinstance(critere, str) or not critere.strip():
            raise ValueError("Nom de critere invalide")

        coefficient = nombre_fini(valeur)

        if coefficient is None or coefficient <= 0:
            raise ValueError(
                f"Coefficient invalide : {critere}"
            )

        coefficients.append(coefficient)

    try:
        total = math.fsum(coefficients)
    except (OverflowError, ValueError):
        raise ValueError(
            "Somme des coefficients invalide"
        ) from None

    if not math.isfinite(total) or total <= 0:
        raise ValueError(
            "Somme des coefficients invalide"
        )

    for coefficient in coefficients:
        if not math.isfinite(coefficient / total):
            raise ValueError(
                "Normalisation des poids invalide"
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
        return False, "Identifiant de course invalide"

    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"

    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"

    depart = course.get("depart")

    if (
        not isinstance(depart, str)
        or not FORMAT_DEPART.fullmatch(depart)
    ):
        return False, "Format ISO du depart invalide"

    try:
        date_depart = datetime.fromisoformat(
            depart.replace("Z", "+00:00")
        )

        if (
            date_depart.tzinfo is None
            or date_depart.utcoffset() is None
        ):
            return False, "Fuseau horaire absent"

        if date_depart <= datetime.now(timezone.utc):
            return False, "Depart deja passe"

    except (ValueError, TypeError, OverflowError):
        return False, "Date de depart invalide"

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
        non_partant = cheval.get("non_partant")

        if type(numero) is not int or numero <= 0:
            return False, "Numero de cheval invalide"

        if numero in numeros:
            return False, "Numero de cheval en double"

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
            return False, (
                "Nombre de partants actifs incoherent"
            )

    if "non_partants" in course:
        liste = course["non_partants"]

        if not isinstance(liste, list):
            return False, "Liste des non-partants invalide"

        if any(type(n) is not int for n in liste):
            return False, "Numero de non-partant invalide"

        if len(liste) != len(set(liste)):
            return False, "Non-partants en double"

        if set(liste) != non_partants:
            return False, (
                "Liste des non-partants incoherente"
            )

    return True, "Course verifiee"


# ============================================================
# 5. EMPREINTE DE CONFIGURATION
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
        total_poids = verifier_configuration(
            "MOTEUR",
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

    for critere, poids_critere in poids.items():

        note = note_valide(donnees.get(critere))

        if note is None:
            continue

        coefficient = float(poids_critere)
        coefficient_normalise = coefficient / total_poids

        criteres[critere] = note
        coefficients.append(coefficient_normalise)
        contributions.append(
            note * coefficient_normalise
        )

    couverture = math.fsum(coefficients)
    couverture = min(1.0, max(0.0, couverture))

    seuil = float(couverture_min)

    admissible = (
        couverture > 0
        and couverture + 1e-12 >= seuil
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
# 7. ANALYSE COMPLETE
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
        positions.append({
            "position_predite": position,
            "numero": cheval["numero"],
            "nom": cheval["nom"],
            "score": cheval["score"],
            "couverture": cheval["couverture"],
            "risques": cheval["risques"],
        })

    if len(admissibles) >= 5:
        resultat["classement"] = positions
        resultat["statut"] = STATUT_DISPONIBLE
        resultat["raison"] = (
            "Cinq positions calculees sur "
            "indicateurs fournis. "
            "Prediction non garantie."
        )

    else:
        resultat["classement_partiel"] = positions
        resultat["statut"] = STATUT_INSUFFISANT
        resultat["raison"] = (
            "Moins de cinq chevaux admissibles. "
            "Classement partiel conserve."
        )

    return resultat


# ============================================================
# 8. VERIFICATION DES SORTIES M1 A M5
# ============================================================

def verifier_sortie_analyse(
    resultat: dict,
    course: dict | None = None,
) -> dict:
    """
    Valide une sortie sans modifier son contenu.

    Controle :
    - statut et version ;
    - absence de FIGE et publication ;
    - positions predites ;
    - doublons ;
    - scores et couvertures ;
    - correspondance avec les analyses ;
    - partants actifs si course fournie.

    Retourne le resultat valide.
    Le controle ne certifie pas l'origine
    des donnees sportives.
    """

    if not isinstance(resultat, dict):
        raise ValueError("Resultat invalide")

    moteur = resultat.get("moteur")

    if not isinstance(moteur, str) or not moteur.strip():
        raise ValueError("Identite moteur invalide")

    if str(resultat.get("version")) != VERSION:
        raise ValueError("Version incompatible")

    statut = resultat.get("statut")

    if statut not in STATUTS_VALIDES:
        raise ValueError("Statut invalide")

    if resultat.get("fige") is not False:
        raise ValueError("FIGE interdit")

    if resultat.get("publication") is not False:
        raise ValueError("Publication interdite")

    classement = resultat.get("classement")
    partiel = resultat.get("classement_partiel")

    if not isinstance(classement, list):
        raise ValueError("Classement invalide")

    if not isinstance(partiel, list):
        raise ValueError("Classement partiel invalide")

    if statut == STATUT_DISPONIBLE:
        if len(classement) != 5 or partiel:
            raise ValueError(
                "Cinq positions obligatoires"
            )

    elif statut == STATUT_INSUFFISANT:
        if classement or len(partiel) >= 5:
            raise ValueError(
                "Classement partiel incoherent"
            )

    elif classement or partiel:
        raise ValueError(
            "Classement interdit pour ce statut"
        )

    actifs = None
    noms_actifs = {}

    if course is not None:

        valide, raison = verifier_course(course)

        if not valide:
            raise ValueError(
                "Course invalide : " + raison
            )

        if resultat.get("course_id") != course.get("id"):
            raise ValueError(
                "Identifiant de course incoherent"
            )

        actifs = set()

        for cheval in course["partants"]:
            if cheval["non_partant"]:
                continue

            numero = cheval["numero"]
            actifs.add(numero)
            noms_actifs[numero] = cheval["nom"]

    analyses = resultat.get("chevaux_analyses")

    if not isinstance(analyses, list):
        raise ValueError(
            "Analyses individuelles invalides"
        )

    analyses_par_numero = {}

    for analyse in analyses:

        if not isinstance(analyse, dict):
            raise ValueError(
                "Analyse individuelle invalide"
            )

        numero = analyse.get("numero")

        if (
            type(numero) is not int
            or numero <= 0
            or numero in analyses_par_numero
        ):
            raise ValueError(
                "Numero d'analyse invalide"
            )

        if actifs is not None and numero not in actifs:
            raise ValueError(
                "Analyse d'un cheval non-partant"
            )

        nom = analyse.get("nom")

        if not isinstance(nom, str) or not nom.strip():
            raise ValueError("Nom d'analyse invalide")

        score = analyse.get("score")

        if score is not None and note_valide(score) is None:
            raise ValueError("Score d'analyse invalide")

        couverture = nombre_fini(
            analyse.get("couverture")
        )

        if (
            couverture is None
            or not 0 <= couverture <= 1
        ):
            raise ValueError(
                "Couverture d'analyse invalide"
            )

        if type(analyse.get("admissible")) is not bool:
            raise ValueError(
                "Admissibilite invalide"
            )

        if actifs is not None:
            if nom != noms_actifs[numero]:
                raise ValueError(
                    "Nom d'analyse incoherent"
                )

        analyses_par_numero[numero] = analyse

    numeros_classes = set()

    for liste in (classement, partiel):

        for position, cheval in enumerate(
            liste,
            start=1,
        ):

            if not isinstance(cheval, dict):
                raise ValueError(
                    "Position invalide"
                )

            numero = cheval.get("numero")
            rang = cheval.get("position_predite")

            if type(numero) is not int or numero <= 0:
                raise ValueError(
                    "Numero classe invalide"
                )

            if numero in numeros_classes:
                raise ValueError(
                    "Cheval classe en double"
                )

            numeros_classes.add(numero)

            if type(rang) is not int or rang != position:
                raise ValueError(
                    "Position predite incoherente"
                )

            if numero not in analyses_par_numero:
                raise ValueError(
                    "Classement sans analyse"
                )

            analyse = analyses_par_numero[numero]

            if analyse["admissible"] is not True:
                raise ValueError(
                    "Cheval non admissible classe"
                )

            if cheval.get("nom") != analyse["nom"]:
                raise ValueError(
                    "Nom classe incoherent"
                )

            score = note_valide(cheval.get("score"))

            if score is None:
                raise ValueError(
                    "Score classe invalide"
                )

            if score != analyse["score"]:
                raise ValueError(
                    "Score classe incoherent"
                )

            couverture = nombre_fini(
                cheval.get("couverture")
            )

            if (
                couverture is None
                or not 0 < couverture <= 1
            ):
                raise ValueError(
                    "Couverture classe invalide"
                )

            if actifs is not None and numero not in actifs:
                raise ValueError(
                    "Cheval non-partant classe"
                )

    json.dumps(
        resultat,
        ensure_ascii=False,
        allow_nan=False,
    )

    return resultat


# ============================================================
# 9. SECURITE JSON
# ============================================================

def refuser_doublons(paires: list) -> dict:

    resultat = {}

    for cle, valeur in paires:

        if cle in resultat:
            raise ValueError(
                f"Cle JSON dupliquee : {cle}"
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
# 10. EXECUTION EN LECTURE SEULE
# ============================================================

def executer(
    analyse: Callable[[Any], dict],
) -> int:

    parser = argparse.ArgumentParser(
        description=(
            "X1000 V2.4 - Analyse hippique "
            "en lecture seule"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Fichier JSON de course verifiee",
    )

    args = parser.parse_args()

    try:

        if not callable(analyse):
            raise ValueError(
                "Fonction d'analyse invalide"
            )

        chemin = Path(args.input)

        course, empreinte = charger_json_securise(
            chemin
        )

        resultat = analyse(course)

        if not isinstance(resultat, dict):
            raise ValueError(
                "Resultat d'analyse invalide"
            )

        verifier_sortie_analyse(
            resultat,
            course if isinstance(course, dict) else None,
        )

        resultat = dict(resultat)
        resultat["source_sha256"] = empreinte

        sortie = json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )

        print(sortie)

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
    ) as erreur:

        print(
            f"Erreur X1000 : {erreur}",
            file=sys.stderr,
        )

        return 1
