#!/usr/bin/env python3
"""X1000 - Validation stricte des courses réelles."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "tests" / "donnees_reelles"

def exiger(ok, message):
    if not ok:
        raise ValueError(message)

def date_iso(valeur):
    exiger(isinstance(valeur, str), "Date absente")
    date = datetime.fromisoformat(
        valeur.replace("Z", "+00:00")
    )
    exiger(
        date.tzinfo is not None
        and date.utcoffset() is not None,
        "Fuseau horaire obligatoire"
    )
    return date

def valider(fichier):
    data = json.loads(fichier.read_text(encoding="utf-8"))
    exiger(isinstance(data, dict), "JSON racine invalide")

    preuve = data.get("preuve")
    course = data.get("course")
    exiger(isinstance(preuve, dict), "Preuve absente")
    exiger(isinstance(course, dict), "Course absente")

    url = preuve.get("source_url", "")
    adresse = urlparse(url)
    exiger(
        adresse.scheme == "https"
        and bool(adresse.hostname)
        and not adresse.username
        and not adresse.password,
        "URL de preuve HTTPS invalide"
    )
    exiger(
        isinstance(preuve.get("source_nom"), str)
        and bool(preuve["source_nom"].strip()),
        "Nom de source absent"
    )
    exiger(
        preuve.get("verification_humaine") is True,
        "Attestation humaine absente"
    )

    date_iso(preuve.get("date_verification"))

    identifiant = course.get("id")
    exiger(
        isinstance(identifiant, str)
        and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}-R\d+-C\d+",
            identifiant
        ) is not None,
        "Identifiant R/C invalide"
    )

    depart = date_iso(course.get("depart"))
    exiger(
        identifiant[:10] == depart.date().isoformat(),
        "Date et identifiant incoherents"
    )

    exiger(
        course.get("localisation_france_verifiee") is True,
        "Localisation France non attestee"
    )
    exiger(
        course.get("depart_verifie") is True,
        "Depart non atteste"
    )

    partants = course.get("partants")
    exiger(
        isinstance(partants, list) and len(partants) >= 5,
        "Partants insuffisants"
    )

    numeros = set()
    actifs = set()
    non_partants = set()

    for cheval in partants:
        exiger(isinstance(cheval, dict), "Cheval invalide")
        numero = cheval.get("numero")
        exiger(
            type(numero) is int and numero > 0
            and numero not in numeros,
            "Numero invalide ou duplique"
        )
        numeros.add(numero)
        exiger(
            isinstance(cheval.get("nom"), str)
            and bool(cheval["nom"].strip()),
            "Nom de cheval absent"
        )
        exiger(
            type(cheval.get("non_partant")) is bool,
            "Statut non-partant absent"
        )
        if cheval["non_partant"]:
            non_partants.add(numero)
        else:
            actifs.add(numero)

    exiger(len(actifs) >= 5, "Moins de 5 actifs")

    if "nombre_partants" in course:
        exiger(
            course["nombre_partants"] == len(actifs),
            "Nombre de partants incoherent"
        )
    if "non_partants" in course:
        exiger(
            set(course["non_partants"]) == non_partants,
            "Liste des non-partants incoherente"
        )

    # Le noyau V2.4 ne traite pas les departs passes.
    exiger(
        depart > datetime.now(timezone.utc),
        "Course historique : analyse prospective interdite"
    )

    # Les criteres ne sont jamais completes artificiellement.
    from moteurs import m1, m2, m3, m4, m5
    for moteur in (m1, m2, m3, m4, m5):
        champ = moteur.CHAMP
        criteres = moteur.POIDS
        complets = 0
        for cheval in partants:
            if cheval["numero"] not in actifs:
                continue
            notes = cheval.get(champ)
            if not isinstance(notes, dict):
                continue
            if all(
                type(notes.get(c)) in (int, float)
                and 0 <= notes[c] <= 100
                for c in criteres
            ):
                complets += 1

        exiger(
            complets >= 5,
            f"{moteur.MOTEUR} : moins de 5 chevaux "
            "avec indicateurs complets"
        )

    print("COURSE ADMISSIBLE :", identifiant)
    print("SOURCE DECLAREE :", url)
    print("CONTROLE DE SOURCE EN LIGNE : NON EFFECTUE")
    return True

def main():
    fichiers = sorted(DOSSIER.glob("*.json"))
    if not fichiers:
        print("AUCUNE COURSE ATTESTEE")
        return 2

    for fichier in fichiers:
        print("VERIFICATION :", fichier.name)
        valider(fichier)

    print("VALIDATION STRUCTURELLE TERMINEE")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erreur:
        print("ERREUR :", erreur, file=sys.stderr)
        sys.exit(1)
