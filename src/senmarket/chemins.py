"""Chemins et partitions du projet SenMarket.

Règle du projet : aucun autre module ne construit un chemin à la main.
Ce module CALCULE des chemins ; il ne crée aucun dossier, sauf
``creer_partition`` qui le fait explicitement.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# chemins.py est dans <racine>/src/senmarket/ : la racine est 2 niveaux au-dessus.
RACINE_PROJET: Final[Path] = Path(__file__).resolve().parents[2]

COUCHES: Final[tuple[str, ...]] = ("raw", "processed", "rejected")
FORMAT_DATE: Final[str] = "%Y-%m-%d"


def charger_env() -> None:
    """Charge le fichier .env de la racine, sans écraser les variables déjà définies."""
    load_dotenv(RACINE_PROJET / ".env", override=False)


def normaliser_date(run_date: date | str) -> str:
    """Retourne la date au format strict AAAA-MM-JJ.

    On utilise ``strptime`` et non ``date.fromisoformat`` : depuis Python 3.11,
    ce dernier accepte aussi « 20261105 » ou « 2026-W45-4 », donc des
    partitions de formats différents pourraient coexister.
    """
    if isinstance(run_date, date):  # datetime est un sous-type de date
        return run_date.strftime(FORMAT_DATE)
    try:
        return datetime.strptime(run_date, FORMAT_DATE).strftime(FORMAT_DATE)
    except ValueError as exc:
        raise ValueError(f"Date invalide {run_date!r} : attendu AAAA-MM-JJ") from exc


def racine_donnees() -> Path:
    """Dossier racine des données, lu dans SENMARKET_DATA_DIR (défaut : ``data``).

    Un chemin relatif est résolu par rapport à la racine du projet, pas par
    rapport au dossier courant : sinon le même script écrirait ailleurs selon
    l'endroit d'où on le lance (notebooks/, tests/, cron...).
    """
    charger_env()
    chemin = Path(os.environ.get("SENMARKET_DATA_DIR", "data")).expanduser()
    if not chemin.is_absolute():
        chemin = RACINE_PROJET / chemin
    return chemin.resolve()


def partition(couche: str, run_date: date | str) -> Path:
    """Chemin ``<données>/<couche>/date=AAAA-MM-JJ`` (n'est pas créé)."""
    if couche not in COUCHES:
        raise ValueError(f"Couche inconnue {couche!r} : choisir parmi {COUCHES}")
    return racine_donnees() / couche / f"date={normaliser_date(run_date)}"


def creer_partition(couche: str, run_date: date | str) -> Path:
    """Crée (si besoin) la partition et retourne son chemin."""
    chemin = partition(couche, run_date)
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def dossier_logs() -> Path:
    """Dossier des journaux d'exécution (ignoré par Git)."""
    return RACINE_PROJET / "logs"


def chemin_log(run_date: date | str, dossier: Path | None = None) -> Path:
    """Chemin ``logs/pipeline_AAAA-MM-JJ.log``."""
    base = dossier if dossier is not None else dossier_logs()
    return base / f"pipeline_{normaliser_date(run_date)}.log"
