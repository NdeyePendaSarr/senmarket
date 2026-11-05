"""Tests de senmarket.chemins."""

from datetime import date, datetime
from pathlib import Path

import pytest

from senmarket import chemins


@pytest.fixture(autouse=True)
def donnees_dans_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige les données vers un dossier temporaire (jamais le vrai data/)."""
    racine = tmp_path / "donnees"
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(racine))
    return racine


@pytest.mark.parametrize("couche", ["raw", "processed", "rejected"])
def test_partition_forme_attendue(couche: str, donnees_dans_tmp: Path) -> None:
    attendu = donnees_dans_tmp.resolve() / couche / "date=2026-11-05"
    assert chemins.partition(couche, "2026-11-05") == attendu


def test_partition_ne_cree_aucun_dossier(donnees_dans_tmp: Path) -> None:
    chemins.partition("raw", "2026-11-05")
    assert not donnees_dans_tmp.exists()


def test_creer_partition_cree_le_dossier() -> None:
    chemin = chemins.creer_partition("raw", "2026-11-05")
    assert chemin.is_dir()


def test_couche_inconnue_leve_valueerror() -> None:
    with pytest.raises(ValueError, match="Couche inconnue"):
        chemins.partition("bronze", "2026-11-05")


@pytest.mark.parametrize("mauvaise", ["2026-13-01", "05/11/2026", "20261105", ""])
def test_date_invalide_leve_valueerror(mauvaise: str) -> None:
    with pytest.raises(ValueError, match="AAAA-MM-JJ"):
        chemins.normaliser_date(mauvaise)


def test_date_et_datetime_acceptes() -> None:
    assert chemins.normaliser_date(date(2026, 11, 5)) == "2026-11-05"
    assert chemins.normaliser_date(datetime(2026, 11, 5, 23, 59)) == "2026-11-05"


def test_chemin_relatif_resolu_depuis_la_racine_du_projet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENMARKET_DATA_DIR", "./donnees_test")
    assert chemins.racine_donnees() == (chemins.RACINE_PROJET / "donnees_test").resolve()


def test_nom_du_fichier_de_log(tmp_path: Path) -> None:
    assert chemins.chemin_log("2026-11-05", tmp_path) == tmp_path / "pipeline_2026-11-05.log"
