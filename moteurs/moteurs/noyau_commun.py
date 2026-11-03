#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2 — Noyau commun d'analyse, sans écriture ni publication.

Les indicateurs de 0 à 100 doivent provenir de données documentées.
Ce module ne collecte pas les données PMU et ne crée pas de FIGÉ.
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "2.2"
TAILLE_MAX_OCTETS = 5 * 1024 * 1024


def maintenant():
    return datetime.now(timezone.utc).isoformat()


def note_valide(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    try:
        nombre = float(valeur)
    except (ValueError, TypeError, OverflowError):
        return None
    return nombre if math.isfinite(nombre) and 0 <= nombre <= 100 else None


def verifier_configuration(moteur, poids, champ, couverture_min):
    if not isinstance(moteur, str) or not moteur.strip():
        raise ValueError("Nom du moteur invalide")
    if not isinstance(champ, str) or not champ.strip():
        raise ValueError("Champ d'analyse invalide")
    if not isinstance(poids, dict) or not poids:
        raise ValueError("Ponderations absentes")
    if isinstance(couverture_min, bool) or not isinstance(couverture_min, (int, float)):
        raise ValueError("Couverture minimale invalide")
    if not math.isfinite(couverture_min) or not 0 < couverture_min <= 1:
        raise ValueError("Couverture minimale hors de ]0, 1]")
    total = 0.0
    for critere, coefficient in poids.items():
        if not isinstance(critere, str) or not critere.strip():
            raise ValueError("Nom de critere invalide")
        if isinstance(coefficient, bool) or not isinstance(coefficient, (int, float)):
            raise ValueError(f"Coefficient invalide : {critere}")
        if not math.isfinite(coefficient) or coefficient <= 0:
            raise ValueError(f"Coefficient non positif : {critere}")
        total += coefficient
    if not math.isfinite(total) or total <= 0:
        raise ValueError("Somme des coefficients invalide")
    return total


def verifier_course(course):
    if not isinstance(course, dict):
        return False, "Format de course invalide"
    identifiant = course.get("id")
    if (isinstance(identifiant, bool) or not isinstance(identifiant, (str, int))
            or not str(identifiant).strip()):
        return False, "Identifiant de course invalide"
    if course.get("localisation_france_verifiee") is not True:
        return False, "Localisation France non verifiee"
    if course.get("depart_verifie") is not True:
        return False, "Depart non verifie"
    depart = course.get("depart")
    if not isinstance(depart, str) or not depart.strip():
        return False, "Date de depart absente"
    try:
        # La date doit contenir une heure explicite et un décalage UTC.
        if "T" not in depart and "t" not in depart:
            return False, "Heure de depart absente"
        date = datetime.fromisoformat(depart.replace("Z", "+00:00"))
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
    for cheval in partants:
        if not isinstance(cheval, dict):
            return False, "Cheval invalide"
        numero, nom, np = (cheval.get("numero"), cheval.get("nom"),
                           cheval.get("non_partant"))
        if type(numero) is not int or numero <= 0:
            return False, "Numero invalide"
        if numero in numeros:
            return False, "Numero en double"
        numeros.add(numero)
        if not isinstance(nom, str) or not nom.strip():
            return False, "Nom invalide"
        if not isinstance(np, bool):
            return False, "Statut non-partant invalide"
        if not np:
            actifs += 1
    if actifs < 5:
        return False, "Moins de cinq partants actifs"
    if "nombre_partants" in course:
        if type(course["nombre_partants"]) is not int or course["nombre_partants"] != actifs:
            return False, "Nombre de partants actifs incoherent"
    if "non_partants" in course:
        np_liste = course["non_partants"]
        if not isinstance(np_liste, list) or any(type(n) is not int for n in np_liste):
            return False, "Liste des non-partants invalide"
        if len(np_liste) != len(set(np_liste)) or set(np_liste) != {
                c["numero"] for c in partants if c["non_partant"]}:
            return False, "Liste des non-partants incoherente"
    return True, "Course verifiee"


def analyser_cheval(cheval, champ, poids, couverture_min, poids_total=None):
    if poids_total is None:
        poids_total = verifier_configuration("MOTEUR", poids, champ, couverture_min)
    donnees = cheval.get(champ)
    if not isinstance(donnees, dict):
        donnees = {}
    details, total, poids_disponible = {}, 0.0, 0.0
    for critere, coefficient in poids.items():
        valeur = note_valide(donnees.get(critere))
        if valeur is None:
            continue
        details[critere] = valeur
        total += valeur * coefficient
        poids_disponible += coefficient
    couverture_brute = poids_disponible / poids_total
    admissible = poids_disponible > 0 and couverture_brute + 1e-12 >= couverture_min
    score = round(total / poids_disponible, 2) if admissible else None
    risques = [{"critere": cle, "note": valeur, "motif": "Indicateur faible"}
               for cle, valeur in details.items() if valeur < 40]
    return {
        "numero": cheval["numero"], "nom": cheval["nom"],
        "score": score, "couverture": round(couverture_brute, 4),
        "criteres": details,
        "criteres_manquants": [cle for cle in poids if cle not in details],
        "risques": risques, "admissible": admissible,
    }


def analyser_course(course, moteur, poids, champ, couverture_min=0.60):
    poids_total = verifier_configuration(moteur, poids, champ, couverture_min)
    valide, raison = verifier_course(course)
    resultat = {
        "moteur": moteur, "version": VERSION,
        "course_id": course.get("id") if isinstance(course, dict) else None,
        "analyse_a": maintenant(), "statut": "NON_ANALYSABLE",
        "raison": raison, "classement": [], "classement_partiel": [],
        "chevaux_analyses": [], "chevaux_evalues": 0,
        "alertes_risques": [], "outsiders_potentiels": [],
        "favoris_a_examiner": [], "fige": False, "publication": False,
    }
    if not valide:
        return resultat
    analyses = [analyser_cheval(c, champ, poids, couverture_min, poids_total)
                for c in course["partants"] if not c["non_partant"]]
    resultat["chevaux_analyses"] = analyses
    admissibles = sorted((c for c in analyses if c["admissible"]),
                         key=lambda c: (-c["score"], -c["couverture"], c["numero"]))
    resultat["chevaux_evalues"] = len(admissibles)
    classement = [{"position_predite": i, "numero": c["numero"],
                   "nom": c["nom"], "score": c["score"],
                   "couverture": c["couverture"], "risques": c["risques"]}
                  for i, c in enumerate(admissibles[:5], 1)]
    resultat["alertes_risques"] = [
        {"numero": c["numero"], "nom": c["nom"], "risques": c["risques"]}
        for c in analyses if c["risques"]]
    if len(admissibles) >= 5:
        resultat["classement"] = classement
        resultat["statut"] = "ANALYSE_DISPONIBLE"
        resultat["raison"] = "Cinq positions calculees sur indicateurs fournis ; prediction non garantie."
    else:
        resultat["classement_partiel"] = classement
        resultat["statut"] = "DONNEES_INSUFFISANTES"
        resultat["raison"] = "Moins de cinq chevaux suffisamment documentes. Aucun classement complet."
    return resultat


def executer(analyse):
    parser = argparse.ArgumentParser(description="X1000 V2 - Analyse hippique en lecture seule")
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    try:
        chemin = Path(args.input)
        if chemin.stat().st_size > TAILLE_MAX_OCTETS:
            raise ValueError("Fichier JSON trop volumineux")
        contenu = chemin.read_bytes()
        if len(contenu) > TAILLE_MAX_OCTETS:
            raise ValueError("Fichier JSON trop volumineux")
        course = json.loads(contenu.decode("utf-8"),
                            parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Constante JSON interdite: " + x)))
        resultat = analyse(course)
        if not isinstance(resultat, dict) or "statut" not in resultat:
            raise ValueError("Resultat d'analyse invalide")
        resultat["source_sha256"] = hashlib.sha256(contenu).hexdigest()
        print(json.dumps(resultat, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if resultat["statut"] == "ANALYSE_DISPONIBLE" else 2
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError, KeyError) as erreur:
        print(f"Erreur X1000 : {erreur}", file=sys.stderr)
        return 1
