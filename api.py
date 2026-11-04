#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
X1000 INTELLIGENCE HIPPIQUE V2
API Python — Lecture seule

- Courses PMU physiquement disputées en France
- Cinq moteurs indépendants M1 à M5
- Six endpoints JSON
- Aucun téléchargement automatique PMU
- Aucun FIGE automatique
- Aucune publication de pronostics
- Aucune validation officielle automatique
- Conservation des archives existantes
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ==========================================
# CONFIGURATION
# ==========================================

APP_NAME = "X1000 Intelligence Hippique V2"
APP_VERSION = "2.0.0"

DATA_DIR = Path(
    os.environ.get("X1000_DATA_DIR", "data")
).resolve()

ALLOWED_ORIGINS = [
    "https://yadcaf-cloud.github.io"
]

MOTEURS = ("M1", "M2", "M3", "M4", "M5")

FICHIERS = {
    "courses": "courses.json",
    "selections": "selections.json",
    "figes": "figes.json",
    "audits": "audits.json",
    "diagnostic": "import_diagnostic.json",
}

# ==========================================
# APPLICATION
# ==========================================

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API X1000 V2 en lecture seule. "
        "Aucune collecte ni validation automatique."
    ),
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

# ==========================================
# LECTURE SECURISEE
# ==========================================

def lire_json(nom):
    if nom not in FICHIERS:
        raise HTTPException(
            status_code=404,
            detail="Ressource inconnue"
        )

    chemin = DATA_DIR / FICHIERS[nom]

    if not chemin.is_file():
        return {
            "disponible": False,
            "donnees": [],
            "raison": "FICHIER_ABSENT"
        }

    try:
        with chemin.open(
            "r", encoding="utf-8"
        ) as fichier:
            contenu = json.load(fichier)

        return {
            "disponible": True,
            "donnees": contenu
        }

    except (OSError, ValueError):
        return {
            "disponible": False,
            "donnees": [],
            "raison": "LECTURE_IMPOSSIBLE"
        }

# ==========================================
# ETATS INDEPENDANTS M1 A M5
# ==========================================

def etat_moteur(nom):
    chemin = DATA_DIR / "moteurs" / (
        nom.lower() + "_status.json"
    )

    if not chemin.is_file():
        return {
            "moteur": nom,
            "etat": "NON_RENSEIGNE",
            "analyse_disponible": False,
            "derniere_actualisation": None
        }

    try:
        with chemin.open(
            "r", encoding="utf-8"
        ) as fichier:
            donnees = json.load(fichier)

        if not isinstance(donnees, dict):
            raise ValueError("Format invalide")

        etat = donnees.get(
            "etat", "NON_RENSEIGNE"
        )

        if etat not in (
            "OPERATIONNEL",
            "SANS_DONNEES",
            "INDISPONIBLE",
            "NON_RENSEIGNE",
        ):
            etat = "NON_RENSEIGNE"

        return {
            "moteur": nom,
            "etat": etat,
            "analyse_disponible": (
                donnees.get(
                    "analyse_disponible"
                ) is True
            ),
            "derniere_actualisation": (
                donnees.get(
                    "derniere_actualisation"
                )
            )
        }

    except (OSError, ValueError):
        return {
            "moteur": nom,
            "etat": "INDISPONIBLE",
            "analyse_disponible": False,
            "derniere_actualisation": None
        }


def etats_moteurs():
    return {
        nom: etat_moteur(nom)
        for nom in MOTEURS
    }

# ==========================================
# SECURITE : LECTURE SEULE
# ==========================================

@app.middleware("http")
async def bloquer_modifications(
    request: Request,
    call_next
):
    if request.method not in (
        "GET", "HEAD", "OPTIONS"
    ):
        return JSONResponse(
            status_code=405,
            content={
                "erreur": "LECTURE_SEULE",
                "message": (
                    "Modification interdite "
                    "sur cette API."
                )
            }
        )

    return await call_next(request)

# ==========================================
# ENDPOINT 1 : STATUS
# ==========================================

@app.get("/api/status")
def api_status():
    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "mode": "LECTURE_SEULE_WEB",
        "date_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "moteurs": etats_moteurs(),
        "collecte_automatique": False,
        "figes_automatiques": False,
        "publication_automatique": False,
        "validation_officielle_automatique": False,
    }

# ==========================================
# ENDPOINT 2 : COURSES
# ==========================================

@app.get("/api/courses")
def api_courses():
    return lire_json("courses")

# ==========================================
# ENDPOINT 3 : SELECTIONS
# ==========================================

@app.get("/api/selections")
def api_selections():
    return lire_json("selections")

# ==========================================
# ENDPOINT 4 : FIGES
# ==========================================

@app.get("/api/figes")
def api_figes():
    return lire_json("figes")

# ==========================================
# ENDPOINT 5 : AUDITS
# ==========================================

@app.get("/api/audits")
def api_audits():
    return lire_json("audits")

# ==========================================
# ENDPOINT 6 : DIAGNOSTIC
# ==========================================

@app.get("/api/diagnostic")
def api_diagnostic():
    return {
        "application": APP_NAME,
        "mode": "LECTURE_SEULE_WEB",
        "fichiers": {
            nom: {
                "present": (
                    DATA_DIR / fichier
                ).is_file()
            }
            for nom, fichier in FICHIERS.items()
        },
        "diagnostic_import": lire_json(
            "diagnostic"
        ),
        "moteurs": etats_moteurs(),
        "regles": {
            "collecte_pmu": False,
            "fige_automatique": False,
            "audit_automatique": False,
            "publication_distante": False,
            "modification_archives": False,
        }
    }

# ==========================================
# FIN DU SERVEUR
# ==========================================
