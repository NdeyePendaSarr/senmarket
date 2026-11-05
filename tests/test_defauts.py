"""Tests de l'injection de défauts : le bilan doit dire la vérité sur les données abîmées."""

import numpy as np
import pandas as pd
import pytest

from senmarket.defauts import (
    DEFAUTS_DONNEES,
    PRIX_OUTLIER,
    TAUX_PAR_DEFAUT,
    injecter_defauts,
    resoudre_defauts,
    taux_effectifs,
)
from senmarket.generateur import generer_verite

ROWS = 6000
RUN_DATE = "2026-11-05"
SEED = 42
Tables = dict[str, pd.DataFrame]


@pytest.fixture(scope="module")
def verite() -> Tables:
    return generer_verite(ROWS, RUN_DATE, seed=SEED)


@pytest.fixture(scope="module")
def abime(verite: Tables) -> tuple[Tables, pd.DataFrame]:
    return injecter_defauts(verite, RUN_DATE, ["tous"], None, SEED)


def nb(bilan: pd.DataFrame, defaut: str, colonne: str | None = None) -> int:
    sel = bilan["defaut"] == defaut
    if colonne is not None:
        sel &= bilan["colonne"] == colonne
    return int(bilan.loc[sel, "nb_injecte"].sum())


def test_sans_defaut_rien_ne_change(verite: Tables) -> None:
    tables, bilan = injecter_defauts(verite, RUN_DATE, [], None, SEED)
    assert bilan.empty
    for nom, df in verite.items():
        pd.testing.assert_frame_equal(df, tables[nom].astype(df.dtypes.to_dict()), check_dtype=False)


def test_les_tables_d_entree_ne_sont_pas_modifiees(verite: Tables) -> None:
    avant = {nom: df.copy() for nom, df in verite.items()}
    injecter_defauts(verite, RUN_DATE, ["tous"], None, SEED)
    for nom, df in verite.items():
        pd.testing.assert_frame_equal(df, avant[nom])


def test_doublons_exacts_comptes_comme_dans_le_bilan(
    abime: tuple[Tables, pd.DataFrame], verite: Tables
) -> None:
    tables, bilan = abime
    lignes = tables["lignes_commande"]
    copies = lignes.duplicated(keep="first")
    assert int(copies.sum()) == nb(bilan, "doublon_ligne")
    assert nb(bilan, "doublon_ligne") == round(0.05 * ROWS)
    assert len(lignes) == len(verite["lignes_commande"]) + nb(bilan, "doublon_ligne")
    # La copie suit immédiatement l'original : « garder la première » est bien défini.
    pos = np.flatnonzero(copies.to_numpy())
    assert (lignes["ligne_commande_id"].to_numpy()[pos]
            == lignes["ligne_commande_id"].to_numpy()[pos - 1]).all()


def test_valeurs_manquantes(abime: tuple[Tables, pd.DataFrame], verite: Tables) -> None:
    tables, bilan = abime
    clients = tables["clients"]
    for col in ("nom_client", "email", "ville"):
        ajoutes = int(clients[col].isna().sum() - verite["clients"][col].isna().sum())
        assert ajoutes == nb(bilan, "valeurs_manquantes", col), col
    assert nb(bilan, "valeurs_manquantes", "ville") == nb(bilan, "valeurs_manquantes", "region")
    assert (clients["ville"].isna() == clients["region"].isna()).all()
    assert int(tables["lignes_commande"]["montant_xof"].isna().sum()) == nb(
        bilan, "valeurs_manquantes", "montant_xof")


def test_dates_futures(abime: tuple[Tables, pd.DataFrame]) -> None:
    tables, bilan = abime
    futures = (tables["commandes"]["date_commande"] > pd.Timestamp(RUN_DATE)).sum()
    assert int(futures) == nb(bilan, "date_future") == round(0.02 * len(tables["commandes"]))


def test_montants_en_texte(abime: tuple[Tables, pd.DataFrame]) -> None:
    tables, bilan = abime
    montants = tables["lignes_commande"]["montant_xof"]
    textes = montants[montants.map(lambda v: isinstance(v, str))]
    assert len(textes) == nb(bilan, "montant_texte")
    assert textes.str.fullmatch(r"\d{1,3}( \d{3})* FCFA|\d+ F CFA|\d{1,3}(\.\d{3})* XOF").all()


def test_outliers_et_quantites_invalides(abime: tuple[Tables, pd.DataFrame]) -> None:
    tables, bilan = abime
    lignes = tables["lignes_commande"]
    assert int((lignes["prix_unitaire_xof"] == PRIX_OUTLIER).sum()) == nb(bilan, "outlier")
    assert int((lignes["quantite"] <= 0).sum()) == nb(bilan, "quantite_negative")


def test_encodage_nom_est_reparable(abime: tuple[Tables, pd.DataFrame], verite: Tables) -> None:
    tables, bilan = abime
    avant, apres = verite["clients"]["nom_client"], tables["clients"]["nom_client"]
    abimes = apres[apres.fillna("").str.contains("Ã")]
    assert len(abimes) == nb(bilan, "encodage_nom") > 0
    reparés = abimes.map(lambda s: s.encode("latin-1").decode("utf-8"))
    assert (reparés == avant.loc[abimes.index]).all()


def test_paiements_orphelins(abime: tuple[Tables, pd.DataFrame]) -> None:
    tables, bilan = abime
    orphelins = ~tables["paiements"]["commande_id"].isin(tables["commandes"]["commande_id"])
    assert int(orphelins.sum()) == nb(bilan, "paiement_orphelin") > 0
    assert tables["paiements"]["paiement_id"].is_unique


def test_une_ligne_n_a_qu_un_seul_defaut(abime: tuple[Tables, pd.DataFrame]) -> None:
    """Cause unique par ligne : la quarantaine pourra être comparée exactement au bilan."""
    tables, _ = abime
    lignes = tables["lignes_commande"]
    montant = lignes["montant_xof"]
    texte = montant.map(lambda v: isinstance(v, str))
    manquant = montant.isna()
    outlier = lignes["prix_unitaire_xof"] == PRIX_OUTLIER
    negatif = lignes["quantite"] <= 0
    cumul = texte.astype(int) + manquant.astype(int) + outlier.astype(int) + negatif.astype(int)
    assert cumul.max() <= 1


def test_deterministe_et_independant_de_l_ordre_des_options(verite: Tables) -> None:
    a, bilan_a = injecter_defauts(verite, RUN_DATE, ["outlier", "doublon_ligne"], None, SEED)
    b, bilan_b = injecter_defauts(verite, RUN_DATE, ["doublon_ligne", "outlier"], None, SEED)
    pd.testing.assert_frame_equal(bilan_a, bilan_b)
    pd.testing.assert_frame_equal(a["lignes_commande"], b["lignes_commande"])


def test_graine_differente_autres_lignes_abimees(verite: Tables) -> None:
    a, _ = injecter_defauts(verite, RUN_DATE, ["outlier"], None, 1)
    b, _ = injecter_defauts(verite, RUN_DATE, ["outlier"], None, 2)
    assert not (a["lignes_commande"]["prix_unitaire_xof"].to_numpy()
                == b["lignes_commande"]["prix_unitaire_xof"].to_numpy()).all()


@pytest.mark.parametrize("defaut", DEFAUTS_DONNEES)
def test_taux_reglable(verite: Tables, defaut: str) -> None:
    _, bilan = injecter_defauts(verite, RUN_DATE, [defaut], {defaut: 0.0}, SEED)
    assert (bilan["nb_injecte"] == 0).all()


def test_tous_developpe_les_huit_defauts_de_donnees() -> None:
    assert resoudre_defauts(["tous"]) == DEFAUTS_DONNEES
    assert len(DEFAUTS_DONNEES) == 8
    assert "encodage_latin1" not in resoudre_defauts(["tous"])


def test_noms_et_taux_invalides() -> None:
    with pytest.raises(ValueError, match="inconnu"):
        resoudre_defauts(["inconnu"])
    with pytest.raises(ValueError, match="hors de"):
        taux_effectifs({"outlier": 1.5})
    with pytest.raises(ValueError, match="Pas de taux"):
        taux_effectifs({"encodage_latin1": 0.5})
    assert taux_effectifs({"outlier": 0.2})["outlier"] == 0.2
    assert taux_effectifs(None) == TAUX_PAR_DEFAUT
