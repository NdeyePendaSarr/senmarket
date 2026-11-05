"""Tests de senmarket.journal."""

import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from senmarket.journal import NOM_LOGGER, configurer_logging


@pytest.fixture(autouse=True)
def nettoyer_logger() -> Iterator[None]:
    """Retire les handlers après chaque test pour ne pas polluer les suivants."""
    yield
    logger = logging.getLogger(NOM_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_cree_le_fichier_et_respecte_le_format(tmp_path: Path) -> None:
    fichier = configurer_logging("2026-11-05", "INFO", tmp_path)
    logging.getLogger("senmarket.test").info("bonjour")
    assert fichier.name == "pipeline_2026-11-05.log"
    motif = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO senmarket\.test: bonjour$"
    assert re.match(motif, fichier.read_text(encoding="utf-8").strip())


def test_idempotent_pas_de_lignes_en_double(tmp_path: Path) -> None:
    configurer_logging("2026-11-05", "INFO", tmp_path)
    fichier = configurer_logging("2026-11-05", "INFO", tmp_path)
    logging.getLogger("senmarket.test").info("une seule fois")
    assert fichier.read_text(encoding="utf-8").count("une seule fois") == 1


def test_le_niveau_filtre_les_messages(tmp_path: Path) -> None:
    fichier = configurer_logging("2026-11-05", "WARNING", tmp_path)
    log = logging.getLogger("senmarket.test")
    log.info("ignoré")
    log.warning("gardé")
    texte = fichier.read_text(encoding="utf-8")
    assert "gardé" in texte and "ignoré" not in texte


def test_niveau_lu_dans_l_environnement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SENMARKET_LOG_LEVEL", "DEBUG")
    fichier = configurer_logging("2026-11-05", dossier=tmp_path)
    logging.getLogger("senmarket.test").debug("détail")
    assert "DEBUG" in fichier.read_text(encoding="utf-8")


def test_niveau_invalide_leve_valueerror(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Niveau de log invalide"):
        configurer_logging("2026-11-05", "BAVARD", tmp_path)
