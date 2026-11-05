"""Tests de l'écriture de la partition brute, du journal et de la reproductibilité."""

import hashlib
import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from senmarket.generation import (
    CLES,
    FICHIER_BILAN,
    FICHIER_JOURNAL,
    FICHIERS,
    generer_partition_brute,
    main,
)
from senmarket.journal import NOM_LOGGER

RUN_DATE = "2026-11-05"
ROWS = 3000


@pytest.fixture(autouse=True)
def donnees_dans_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Données et journaux dans un dossier temporaire ; le logger est nettoyé ensuite."""
    racine = tmp_path / "donnees"
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(racine))
    monkeypatch.setattr("senmarket.chemins.dossier_logs", lambda: tmp_path / "logs")
    yield racine
    logger = logging.getLogger(NOM_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def empreintes(dossier: Path) -> dict[str, str]:
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(dossier.iterdir())}


def test_ecrit_les_huit_csv_le_bilan_et_le_journal() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, defauts=["tous"], seed=42)
    assert dossier.name == "date=2026-11-05" and dossier.parent.name == "raw"
    assert sorted(p.name for p in dossier.iterdir()) == sorted(FICHIERS)


def test_deux_executions_donnent_des_fichiers_identiques(tmp_path: Path) -> None:
    premier = generer_partition_brute(ROWS, RUN_DATE, defauts=["tous"], seed=42)
    h1 = empreintes(premier)
    deuxieme = generer_partition_brute(ROWS, RUN_DATE, defauts=["tous"], seed=42, ecraser=True)
    assert h1 == empreintes(deuxieme)  # y compris le journal : aucune heure courante


def test_refuse_d_ecraser_sans_option() -> None:
    generer_partition_brute(ROWS, RUN_DATE, seed=42)
    with pytest.raises(FileExistsError, match="--ecraser"):
        generer_partition_brute(ROWS, RUN_DATE, seed=42)


def test_defaut_inconnu_ne_cree_aucun_dossier(donnees_dans_tmp: Path) -> None:
    with pytest.raises(ValueError, match="inconnu"):
        generer_partition_brute(ROWS, RUN_DATE, defauts=["nimporte"], seed=42)
    assert not donnees_dans_tmp.exists()


def test_sans_defaut_le_bilan_est_vide() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, seed=42)
    assert len(pd.read_csv(dossier / FICHIER_BILAN)) == 0


def test_bilan_coherent_avec_les_taux_demandes() -> None:
    dossier = generer_partition_brute(10_000, RUN_DATE, defauts=["tous"], seed=42)
    bilan = pd.read_csv(dossier / FICHIER_BILAN)
    part = bilan["nb_injecte"] / bilan["nb_lignes_reference"]
    # À 10 000 lignes, chaque taux réalisé est à ±1 point du taux demandé.
    assert ((part - bilan["taux_demande"]).abs() <= 0.01).all()


def test_format_du_journal_et_horodatages_derives_de_la_date() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, defauts=["tous"], seed=42)
    lignes = (dossier / FICHIER_JOURNAL).read_text(encoding="utf-8").splitlines()
    motif = re.compile(r"^2026-11-05 \d{2}:\d{2}:\d{2} (INFO|WARN|ERROR) ingestion: .+$")
    assert all(motif.match(ligne) for ligne in lignes)
    niveaux = {ligne.split()[2] for ligne in lignes}
    assert niveaux == {"INFO", "WARN", "ERROR"}
    assert sum(" ERROR " in ligne for ligne in lignes) >= 2
    assert lignes == sorted(lignes)  # ordre chronologique


def test_les_nombres_du_journal_viennent_de_la_vraie_generation() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, defauts=["tous"], seed=42)
    journal = (dossier / FICHIER_JOURNAL).read_text(encoding="utf-8")
    bilan = pd.read_csv(dossier / FICHIER_BILAN)
    doublons = int(bilan.loc[bilan["defaut"] == "doublon_ligne", "nb_injecte"].iloc[0])
    assert f"{doublons} lignes en double détectées" in journal
    n_lignes = len(pd.read_csv(dossier / "lignes_commande.csv"))
    assert f"lignes_commande: {n_lignes} lignes chargées" in journal


def test_csv_en_utf8_et_lisibles_par_pandas() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, seed=42)
    for nom in CLES:
        df = pd.read_csv(dossier / f"{nom}.csv", encoding="utf-8")
        assert not df.empty
    clients = pd.read_csv(dossier / "clients.csv", encoding="utf-8")
    assert clients["nom_client"].str.contains("[éèïÏôêÂ]", regex=True).any()


def test_defaut_de_fichier_encodage_latin1_echoue_en_utf8() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, defauts=["encodage_latin1"], seed=42)
    with pytest.raises(UnicodeDecodeError):
        (dossier / "clients.csv").read_bytes().decode("utf-8")
    texte = (dossier / "clients.csv").read_text(encoding="latin-1")
    assert any(c in texte for c in "éèïôÂ")  # lisible en Latin-1, illisible en UTF-8


def test_defaut_de_fichier_colonne_manquante() -> None:
    dossier = generer_partition_brute(ROWS, RUN_DATE, defauts=["colonne_manquante"], seed=42)
    entete = (dossier / "lignes_commande.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "prix_unitaire_xof" not in entete and "montant_xof" in entete
    bilan = pd.read_csv(dossier / FICHIER_BILAN)
    assert bilan["defaut"].tolist() == ["colonne_manquante"]


def test_cli_ligne_de_commande(tmp_path: Path, donnees_dans_tmp: Path) -> None:
    code = main(["--run-date", RUN_DATE, "--rows", "1000", "--defauts", "outlier",
                 "--taux", "outlier=0.05"])
    assert code == 0
    bilan = pd.read_csv(donnees_dans_tmp / "raw" / "date=2026-11-05" / FICHIER_BILAN)
    assert bilan["nb_injecte"].tolist() == [50]
    assert main(["--run-date", RUN_DATE, "--rows", "1000"]) == 1  # existe déjà, pas d'écrasement
    assert main(["--run-date", RUN_DATE, "--rows", "1000", "--ecraser"]) == 0
    assert (tmp_path / "logs" / "pipeline_2026-11-05.log").exists()
