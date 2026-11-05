"""Configuration du logging : console + fichier ``logs/pipeline_AAAA-MM-JJ.log``."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Final

from senmarket.chemins import charger_env, chemin_log

NOM_LOGGER: Final[str] = "senmarket"
FORMAT_LOG: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"
FORMAT_HEURE: Final[str] = "%Y-%m-%d %H:%M:%S"


def _niveau(niveau: str | None) -> int:
    """Résout le niveau : argument, sinon SENMARKET_LOG_LEVEL, sinon INFO."""
    charger_env()
    nom = (niveau or os.environ.get("SENMARKET_LOG_LEVEL", "INFO")).upper()
    niveaux = logging.getLevelNamesMapping()
    if nom not in niveaux or nom == "NOTSET":
        raise ValueError(f"Niveau de log invalide {nom!r}")
    return niveaux[nom]


def configurer_logging(
    run_date: date | str,
    niveau: str | None = None,
    dossier: Path | None = None,
) -> Path:
    """Configure le logger « senmarket » et retourne le chemin du fichier de log.

    Idempotent : l'appeler deux fois ne double pas les lignes, car on retire les
    anciens handlers avant d'en poser de nouveaux.
    """
    fichier = chemin_log(run_date, dossier)
    fichier.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(NOM_LOGGER)
    logger.setLevel(_niveau(niveau))
    for ancien in list(logger.handlers):
        logger.removeHandler(ancien)
        ancien.close()

    formateur = logging.Formatter(FORMAT_LOG, datefmt=FORMAT_HEURE)
    for handler in (
        logging.StreamHandler(),
        logging.FileHandler(fichier, mode="a", encoding="utf-8"),
    ):
        handler.setFormatter(formateur)
        logger.addHandler(handler)
    return fichier
