#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X1000 V2.5 : contrôle technique PMU, sans publication ni FIGÉ.

Collecte HTTPS limitée à la source PMU, uniquement à l'exécution de main().
Aucune validation sportive ou transmission aux moteurs M1-M5.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from audit_collecte_pmu import (
    BASE, RedirectionInterdite, recuperer_json,
    refuser_constante, refuser_doublons,
)

PARIS = ZoneInfo("Europe/Paris")
MAX_COURSES = 150
MAX_PARTICIPANTS = 100
MAX_REPONSE = 5 * 1024 * 1024
MAX_RAPPORT = 10 * 1024 * 1024
STATUTS_NP = {"NON_PARTANT"}
STATUTS_ACTIFS = {"PARTANT", "CONFIRME"}
PAYS_FRANCE = {"FR", "FRA", "FRANCE"}
URL_PARTICIPANTS = re.compile(
    r"https://online\.turfinfo\.api\.pmu\.fr"
    r"/rest/client/1/programme/[0-9]{8}"
    r"/R[1-9][0-9]*/C[1-9][0-9]*/participants\Z"
)


def entier(valeur):
    """Entier strictement positif; booléens et valeurs ambiguës rejetés."""
    if type(valeur) is int and 0 < valeur <= 999_999_999:
        return valeur
    if type(valeur) is str and re.fullmatch(r"[1-9][0-9]{0,8}", valeur):
        return int(valeur)
    return None


def pays_france(reunion):
    """Exige un code France explicite et aucune contradiction."""
    if not isinstance(reunion, dict):
        return False
    objets = [reunion]
    hippo = reunion.get("hippodrome")
    if isinstance(hippo, dict):
        objets.append(hippo)
    codes = []
    for objet in objets:
        for cle in ("pays", "codePays", "code_pays", "countryCode", "country"):
            if cle not in objet or objet[cle] is None:
                continue
            valeur = objet[cle]
            if not isinstance(valeur, str) or not valeur.strip():
                return False
            codes.append(valeur.strip().upper())
    return bool(codes) and all(code in PAYS_FRANCE for code in codes)


def nom_hippodrome(reunion):
    if not isinstance(reunion, dict):
        return ""
    valeur = reunion.get("hippodrome")
    if isinstance(valeur, dict):
        valeur = valeur.get("libelleLong") or valeur.get("libelleCourt")
    return valeur.strip() if isinstance(valeur, str) else ""


def heure_depart(course, jour):
    """Retourne l'heure prévue UTC; jamais une preuve du départ effectif."""
    if not isinstance(course, dict) or not isinstance(jour, date):
        return None
    valeur = course.get("heureDepart")
    if type(valeur) not in (int, float):
        return None
    if not math.isfinite(valeur) or not 1_000_000_000_000 <= valeur <= 9_999_999_999_999:
        return None
    try:
        dt = datetime.fromtimestamp(valeur / 1000, tz=timezone.utc)
        return dt.isoformat() if dt.astimezone(PARIS).date() == jour else None
    except (ValueError, OverflowError, OSError):
        return None


def extraire_partants(donnees):
    if isinstance(donnees, list):
        return donnees
    if isinstance(donnees, dict):
        for cle in ("participants", "partants"):
            if isinstance(donnees.get(cle), list):
                return donnees[cle]
    raise ValueError("Liste participants absente")


def valider_partants(participants):
    if not isinstance(participants, list) or not participants:
        raise ValueError("Aucun participant")
    if len(participants) > MAX_PARTICIPANTS:
        raise ValueError("Trop de participants")
    numeros, actifs, non_partants = set(), [], []
    for participant in participants:
        if not isinstance(participant, dict):
            raise ValueError("Participant invalide")
        numero = entier(participant.get("numPmu"))
        nom = participant.get("nom")
        if numero is None or numero in numeros:
            raise ValueError("Numero absent ou duplique")
        if not isinstance(nom, str) or not nom.strip():
            raise ValueError("Nom du cheval absent")
        numeros.add(numero)
        statut = participant.get("statut")
        indicateur = participant.get("nonPartant")
        preuve_statut = None
        preuve_indicateur = None
        if statut is not None:
            if not isinstance(statut, str):
                raise ValueError("Statut invalide")
            statut = statut.strip().upper()
            if statut in STATUTS_NP:
                preuve_statut = True
            elif statut in STATUTS_ACTIFS:
                preuve_statut = False
            else:
                raise ValueError("Statut non reconnu")
        if indicateur is not None:
            if type(indicateur) is not bool:
                raise ValueError("Indicateur nonPartant invalide")
            preuve_indicateur = indicateur
        if (preuve_statut is not None and preuve_indicateur is not None
                and preuve_statut != preuve_indicateur):
            raise ValueError("Statuts contradictoires")
        if preuve_statut is None and preuve_indicateur is None:
            raise ValueError("Statut non verifiable")
        np = preuve_statut if preuve_statut is not None else preuve_indicateur
        cheval = {"numero": numero, "nom": nom.strip(), "non_partant": np}
        (non_partants if np else actifs).append(cheval)
    if not actifs:
        raise ValueError("Aucun partant actif")
    return actifs, non_partants


def programme_reunions(donnees):
    if not isinstance(donnees, dict):
        raise ValueError("Programme non objet")
    programme = donnees.get("programme", donnees)
    if not isinstance(programme, dict):
        raise ValueError("Programme invalide")
    reunions = programme.get("reunions")
    if not isinstance(reunions, list):
        raise ValueError("Reunions absentes")
    return reunions


def recuperer_participants(url):
    """Télécharge seulement une URL PMU autorisée, sans redirection."""
    if not isinstance(url, str) or URL_PARTICIPANTS.fullmatch(url) is None:
        raise ValueError("URL participants interdite")
    requete = Request(url, headers={
        "Accept": "application/json", "User-Agent": "X1000-V2.5-Audit/1.0"
    }, method="GET")
    try:
        with build_opener(RedirectionInterdite()).open(requete, timeout=15) as reponse:
            if reponse.status != 200:
                raise ValueError("HTTP non 200")
            media = reponse.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if media != "application/json" and not media.endswith("+json"):
                raise ValueError("Reponse non JSON")
            annonce = reponse.headers.get("Content-Length")
            if annonce is not None:
                try:
                    taille = int(annonce)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Content-Length invalide") from exc
                if taille < 0 or taille > MAX_REPONSE:
                    raise ValueError("Taille HTTP interdite")
            raw = reponse.read(MAX_REPONSE + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Collecte participants impossible: {type(exc).__name__}") from exc
    if not raw or len(raw) > MAX_REPONSE:
        raise ValueError("Taille reponse invalide")
    try:
        donnees = json.loads(raw.decode("utf-8-sig"),
                             object_pairs_hook=refuser_doublons,
                             parse_constant=refuser_constante)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("JSON participants invalide") from exc
    return donnees, hashlib.sha256(raw).hexdigest()


def construire_rapport(programme, empreinte, jour, recuperation=recuperer_participants):
    """Construction testable; aucune écriture, aucun FIGÉ ni appel aux moteurs."""
    if not isinstance(jour, date) or isinstance(jour, datetime):
        raise ValueError("Date invalide")
    if not isinstance(empreinte, str) or re.fullmatch(r"[a-fA-F0-9]{64}", empreinte) is None:
        raise ValueError("Empreinte programme invalide")
    date_pmu = jour.strftime("%d%m%Y")
    url = f"{BASE}/programme/{date_pmu}"
    reunions = programme_reunions(programme)
    rapport = {
        "version": "2.5", "statut": "VALIDATION_TECHNIQUE_SANS_PUBLICATION",
        "date": jour.isoformat(), "source": url, "source_sha256": empreinte,
        "collecte_a": datetime.now(timezone.utc).isoformat(),
        "publication": False, "fige": False, "validation_sportive": False,
        "transmission_moteurs": False, "courses_france_verifiees": 0,
        "courses_partielles": 0, "courses_refusees": 0, "courses": [],
    }
    vues = set()
    total = 0
    for reunion in reunions:
        if not isinstance(reunion, dict):
            raise ValueError("Reunion invalide")
        nr = entier(reunion.get("numOfficiel"))
        courses = reunion.get("courses")
        if nr is None or not isinstance(courses, list):
            raise ValueError("Structure reunion invalide")
        for course in courses:
            total += 1
            if total > MAX_COURSES:
                raise ValueError("Limite de courses depassee")
            if not isinstance(course, dict):
                raise ValueError("Course invalide")
            nc = entier(course.get("numOrdre"))
            if nc is None:
                raise ValueError("Numero course absent")
            identifiant = f"R{nr}C{nc}"
            if identifiant in vues:
                raise ValueError("Course dupliquee")
            vues.add(identifiant)
            entree = {
                "id": identifiant, "hippodrome": nom_hippodrome(reunion),
                "localisation_france_verifiee": False,
                "depart_programme_verifie": False,
                "depart_effectif_verifie": False,
                "partants_verifies": False,
                "statut": "REFUSE", "raison": "",
            }
            if not pays_france(reunion):
                entree["raison"] = "Pays France non prouve"
            elif not entree["hippodrome"]:
                entree["raison"] = "Hippodrome non identifiable"
            else:
                entree["localisation_france_verifiee"] = True
                depart = heure_depart(course, jour)
                if depart is None:
                    entree["raison"] = "Horaire non verifiable"
                else:
                    entree["depart_programme_verifie"] = True
                    entree["depart"] = depart
                    url_partants = f"{BASE}/programme/{date_pmu}/R{nr}/C{nc}/participants"
                    try:
                        donnees, sha = recuperation(url_partants)
                        actifs, np = valider_partants(extraire_partants(donnees))
                        if not isinstance(sha, str) or re.fullmatch(r"[a-fA-F0-9]{64}", sha) is None:
                            raise ValueError("Empreinte participants invalide")
                        entree.update({
                            "statut": "OK", "raison": "Donnees techniques controlees",
                            "partants_verifies": True, "nombre_partants": len(actifs),
                            "partants": actifs, "non_partants": np,
                            "participants_sha256": sha,
                        })
                    except (ValueError, OSError, UnicodeError) as exc:
                        entree["raison"] = str(exc)[:200]
            if entree["statut"] == "OK":
                rapport["courses_france_verifiees"] += 1
            elif entree["localisation_france_verifiee"]:
                entree["statut"] = "PARTIEL"
                rapport["courses_partielles"] += 1
            else:
                rapport["courses_refusees"] += 1
            rapport["courses"].append(entree)
    rapport["courses_total"] = total
    return rapport


def main():
    jour = datetime.now(PARIS).date()
    url = f"{BASE}/programme/{jour.strftime('%d%m%Y')}"
    programme, empreinte = recuperer_json(url)
    rapport = construire_rapport(programme, empreinte, jour)
    sortie = json.dumps(rapport, ensure_ascii=False, indent=2, allow_nan=False)
    if len(sortie.encode("utf-8")) > MAX_RAPPORT:
        raise ValueError("Rapport trop volumineux")
    print(sortie)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, HTTPError, URLError, TimeoutError) as erreur:
        print(f"VALIDATION V2.5 REFUSEE : {erreur}", file=sys.stderr)
        raise SystemExit(1)
