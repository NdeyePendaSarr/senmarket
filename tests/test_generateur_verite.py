"""Tests de la « vérité » : le jeu sans défaut doit respecter tous les invariants du contrat."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from senmarket.generateur import generer_verite, graine_entiere

ROWS = 6000
RUN_DATE = "2026-11-05"
JOURS = 365
Tables = dict[str, pd.DataFrame]

CLES = {
    "clients": "client_id", "vendeurs": "vendeur_id", "produits": "produit_id",
    "commandes": "commande_id", "lignes_commande": "ligne_commande_id",
    "paiements": "paiement_id", "avis": "avis_id", "navigation": "evenement_id",
}
PREFIXES = {
    "clients": "CLI", "vendeurs": "VEN", "produits": "PRD", "commandes": "CMD",
    "lignes_commande": "LIG", "paiements": "PAI", "avis": "AVI", "navigation": "NAV",
}


@pytest.fixture(scope="module")
def t() -> Tables:
    return generer_verite(ROWS, RUN_DATE, jours=JOURS, seed=42)


@pytest.mark.parametrize("table", list(CLES))
def test_cle_primaire_unique_et_format(t: Tables, table: str) -> None:
    ids = t[table][CLES[table]]
    assert ids.is_unique
    assert ids.str.fullmatch(PREFIXES[table] + r"\d{7}").all()


@pytest.mark.parametrize(("enfant", "colonne", "parent"), [
    ("produits", "vendeur_id", "vendeurs"),
    ("commandes", "client_id", "clients"),
    ("lignes_commande", "commande_id", "commandes"),
    ("lignes_commande", "produit_id", "produits"),
    ("paiements", "commande_id", "commandes"),
    ("avis", "client_id", "clients"),
    ("avis", "produit_id", "produits"),
    ("avis", "commande_id", "commandes"),
    ("navigation", "client_id", "clients"),
    ("navigation", "produit_id", "produits"),
])
def test_aucune_cle_etrangere_orpheline(
    t: Tables, enfant: str, colonne: str, parent: str
) -> None:
    valeurs = t[enfant][colonne].dropna()  # client_id peut être vide en navigation
    assert valeurs.isin(t[parent][CLES[parent]]).all()


def test_montant_egal_quantite_fois_prix(t: Tables) -> None:
    lg = t["lignes_commande"]
    assert (lg["montant_xof"] == lg["quantite"] * lg["prix_unitaire_xof"]).all()
    assert (lg["quantite"] > 0).all()


def test_prix_paye_dans_plus_ou_moins_10_pourcent_du_catalogue(t: Tables) -> None:
    lg = t["lignes_commande"].merge(t["produits"], on="produit_id")
    cat = lg["prix_catalogue_xof"]
    assert (lg["prix_unitaire_xof"] >= 0.9 * cat).all()
    assert (lg["prix_unitaire_xof"] <= 1.1 * cat).all()
    assert (lg["prix_unitaire_xof"] != cat).any()  # il y a bien des promotions


def test_prix_catalogue_dans_les_bornes(t: Tables) -> None:
    assert t["produits"]["prix_catalogue_xof"].between(1_000, 500_000).all()


def test_les_montants_sont_des_entiers(t: Tables) -> None:
    for table, colonne in [("produits", "prix_catalogue_xof"),
                           ("lignes_commande", "prix_unitaire_xof"),
                           ("lignes_commande", "montant_xof"),
                           ("paiements", "montant_xof")]:
        assert pd.api.types.is_integer_dtype(t[table][colonne]), (table, colonne)


def test_dates_coherentes(t: Tables) -> None:
    run = pd.Timestamp(RUN_DATE)
    debut = run - timedelta(days=JOURS)
    cmd = t["commandes"].merge(t["clients"], on="client_id")
    assert (cmd["date_commande"] >= cmd["date_inscription"]).all()
    assert cmd["date_commande"].between(debut, run).all()
    assert (t["clients"]["date_inscription"] <= run).all()

    pay = t["paiements"].merge(t["commandes"], on="commande_id")
    assert (pay["date_paiement"] >= pay["date_commande"]).all()
    assert (pay["date_paiement"] <= run).all()

    avis = t["avis"].merge(t["commandes"], on="commande_id")
    assert (avis["date_avis"] >= avis["date_commande"]).all()
    assert (avis["date_avis"] <= run).all()

    assert (t["navigation"]["date_evenement"] < run + timedelta(days=1)).all()


def test_un_avis_ne_pointe_que_vers_un_produit_de_sa_commande(t: Tables) -> None:
    paires = set(zip(t["lignes_commande"]["commande_id"], t["lignes_commande"]["produit_id"],
                     strict=True))
    avis = t["avis"]
    assert all((c, p) in paires for c, p in zip(avis["commande_id"], avis["produit_id"],
                                                 strict=True))
    cmd = t["commandes"].set_index("commande_id")["client_id"]
    assert (avis["client_id"].to_numpy() == cmd.loc[avis["commande_id"]].to_numpy()).all()
    livrees = set(t["commandes"].loc[t["commandes"]["statut"] == "livree", "commande_id"])
    assert set(avis["commande_id"]) <= livrees


def test_un_produit_au_plus_une_fois_par_commande(t: Tables) -> None:
    assert not t["lignes_commande"].duplicated(["commande_id", "produit_id"]).any()
    assert t["commandes"]["commande_id"].isin(t["lignes_commande"]["commande_id"]).all()


def test_volumes_conformes_aux_ordres_de_grandeur(t: Tables) -> None:
    assert len(t["lignes_commande"]) == ROWS
    assert len(t["commandes"]) == round(ROWS / 2.5)
    assert len(t["clients"]) == ROWS // 3
    assert len(t["vendeurs"]) == 20 and len(t["produits"]) == 40
    assert len(t["navigation"]) == pytest.approx(2 * ROWS, rel=0.05)


def test_realisme_dakar_domine(t: Tables) -> None:
    part = (t["clients"]["ville"] == "Dakar").mean()
    assert 0.28 < part < 0.39
    assert t["clients"]["ville"].nunique() >= 15


def test_assez_de_clients_recurrents_pour_les_cohortes(t: Tables) -> None:
    """Sinon la rétention et les cohortes du chapitre 5 n'auront aucun sens."""
    par_client = t["commandes"].groupby("client_id").size()
    part_recurrents = (par_client >= 2).mean()
    assert part_recurrents >= 0.15, f"seulement {part_recurrents:.1%} de clients récurrents"
    assert par_client.max() >= 10  # quelques gros clients


def test_paiements_ecarts_metier_presents_mais_rares(t: Tables) -> None:
    n_cmd = len(t["commandes"])
    sans_paiement = 1 - t["paiements"]["commande_id"].nunique() / n_cmd
    assert 0.005 < sans_paiement < 0.04
    assert t["paiements"]["commande_id"].is_unique

    somme = t["lignes_commande"].groupby("commande_id")["montant_xof"].sum()
    comp = t["paiements"].set_index("commande_id")["montant_xof"].to_frame("paye").join(
        somme.rename("lignes"))
    part_ecart = (comp["paye"] != comp["lignes"]).mean()
    assert 0.0 < part_ecart < 0.04


def test_modalites_de_paiement_connues(t: Tables) -> None:
    pay = t["paiements"]
    assert set(pay["methode_paiement"]) <= {"wave", "orange_money", "carte", "especes"}
    assert set(pay["statut_paiement"]) <= {"reussi", "echoue", "en_attente"}
    assert (pay["statut_paiement"] == "reussi").mean() > 0.85


def test_navigation_entonnoir_et_anonymes(t: Tables) -> None:
    nav = t["navigation"]
    sessions = nav.groupby("session_id")["type_evenement"].agg(set)
    assert (sessions.map(lambda s: "debut_paiement" in s).mean()) == pytest.approx(0.15, abs=0.03)
    # Pas d'ajout au panier sans avoir vu un produit, pas de paiement sans panier.
    assert sessions.map(lambda s: "ajout_panier" not in s or "vue_produit" in s).all()
    assert sessions.map(lambda s: "debut_paiement" not in s or "ajout_panier" in s).all()
    part_anonyme = nav.groupby("session_id")["client_id"].first().isna().mean()
    assert part_anonyme == pytest.approx(0.30, abs=0.05)


def test_navigation_ordre_des_evenements_dans_une_session(t: Tables) -> None:
    nav = t["navigation"]
    ordre = {"vue_produit": 0, "ajout_panier": 1, "debut_paiement": 2}
    nav = nav.assign(rang=nav["type_evenement"].map(ordre))
    # Dans chaque session, le rang ne décroît jamais quand on suit le temps.
    assert (nav.groupby("session_id")["rang"].diff().dropna() >= 0).all()


def test_reproductible_meme_graine_meme_date(t: Tables) -> None:
    deuxieme = generer_verite(ROWS, RUN_DATE, jours=JOURS, seed=42)
    for nom in CLES:
        pd.testing.assert_frame_equal(t[nom], deuxieme[nom])


def test_date_ou_graine_differente_donne_autre_jeu(t: Tables) -> None:
    autre_date = generer_verite(ROWS, "2026-11-06", jours=JOURS, seed=42)
    autre_graine = generer_verite(ROWS, RUN_DATE, jours=JOURS, seed=43)
    assert not t["clients"]["nom_client"].equals(autre_date["clients"]["nom_client"])
    assert not t["clients"]["nom_client"].equals(autre_graine["clients"]["nom_client"])


def test_graine_entiere_est_un_seul_entier() -> None:
    assert graine_entiere(42, "2026-11-05") == 4_220_261_105
    assert graine_entiere(42, date(2026, 11, 5)) == 4_220_261_105


@pytest.mark.parametrize(("rows", "jours"), [(9, 365), (1000, 0)])
def test_parametres_invalides(rows: int, jours: int) -> None:
    with pytest.raises(ValueError):
        generer_verite(rows, RUN_DATE, jours=jours, seed=42)


def test_petit_volume_reste_coherent() -> None:
    petit = generer_verite(50, RUN_DATE, jours=30, seed=1)
    assert len(petit["lignes_commande"]) == 50
    assert np.isin(petit["lignes_commande"]["commande_id"], petit["commandes"]["commande_id"]).all()
