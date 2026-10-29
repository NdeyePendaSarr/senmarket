"""Chemins des partitions SenMarket : seul module qui construit un chemin."""
from datetime import date
from pathlib import Path
import os

from dotenv import load_dotenv

COUCHES = ("raw", "processed", "rejected")


def racine_projet() -> Path:
    """Dossier senmarket/, quel que soit le dossier d'où on lance Python."""
    # chemins.py -> src/senmarket/ -> src/ -> senmarket/
    return Path(__file__).resolve().parents[2]


def dossier_donnees() -> Path:
    """Lit SENMARKET_DATA_DIR ; un chemin relatif est pris depuis la racine du projet."""
    load_dotenv(racine_projet() / ".env")
    dossier = Path(os.getenv("SENMARKET_DATA_DIR", "data"))
    if not dossier.is_absolute():
        dossier = racine_projet() / dossier
    return dossier


def valider_date(run_date: str) -> date:
    """Renvoie la date ; lève ValueError avec un message clair si elle est invalide."""
    try:
        return date.fromisoformat(run_date)
    except ValueError:
        raise ValueError(f"Date invalide : {run_date!r} (format attendu : AAAA-MM-JJ)") from None


def partition(couche: str, run_date: str) -> Path:
    """data/<couche>/date=AAAA-MM-JJ. Lève ValueError si la couche ou la date est invalide."""
    if couche not in COUCHES:
        raise ValueError(f"Couche inconnue : {couche!r} (attendu : {', '.join(COUCHES)})")
    jour = valider_date(run_date)
    return dossier_donnees() / couche / f"date={jour.isoformat()}"


def fichier_log(run_date: str) -> Path:
    """logs/pipeline_AAAA-MM-JJ.log, à la racine du projet."""
    jour = valider_date(run_date)
    return racine_projet() / "logs" / f"pipeline_{jour.isoformat()}.log"