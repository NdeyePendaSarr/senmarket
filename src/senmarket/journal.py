"""Configuration du logging : console + fichier, une seule fois par exécution."""
import logging
import os

from dotenv import load_dotenv

from senmarket.chemins import fichier_log, racine_projet

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
FORMAT_DATE = "%Y-%m-%d %H:%M:%S"


def configurer_logging(run_date: str) -> None:
    """Niveau lu dans SENMARKET_LOG_LEVEL ; écrit dans la console et dans le fichier du jour."""
    load_dotenv(racine_projet() / ".env")
    niveau = os.getenv("SENMARKET_LOG_LEVEL", "INFO").upper()

    chemin = fichier_log(run_date)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=niveau,
        format=FORMAT,
        datefmt=FORMAT_DATE,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(chemin, encoding="utf-8"),
        ],
        force=True,
    )