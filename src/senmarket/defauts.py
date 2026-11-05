"""Injection contrôlée de défauts dans la « vérité » (étape 2b).

Règle d'or : on génère propre (``generateur.generer_verite``), PUIS on abîme ici.
Chaque défaut a son propre générateur aléatoire : activer ou désactiver un défaut
ne modifie jamais la vérité, ni les choix des autres défauts indépendants.
Chaque ligne touchée l'est par UN seul défaut (pools disjoints) : la quarantaine
pourra donc être comparée exactement au bilan d'injection.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Final

import numpy as np
import pandas as pd

from senmarket.chemins import normaliser_date
from senmarket.generateur import (
    METHODES,
    P_METHODES,
    P_STATUTS_PAIEMENT,
    STATUTS_PAIEMENT,
)

# Défauts qui modifient les données, dans l'ordre d'application.
DEFAUTS_DONNEES: Final[tuple[str, ...]] = (
    "doublon_ligne", "valeurs_manquantes", "date_future", "montant_texte",
    "outlier", "quantite_negative", "encodage_nom", "paiement_orphelin",
)
# Défauts de fichier : appliqués à l'écriture, désactivés par défaut (épreuve du chapitre 4).
DEFAUTS_FICHIER: Final[tuple[str, ...]] = ("encodage_latin1", "colonne_manquante")
CATALOGUE: Final[tuple[str, ...]] = DEFAUTS_DONNEES + DEFAUTS_FICHIER

TAUX_PAR_DEFAUT: Final[dict[str, float]] = {
    "doublon_ligne": 0.05, "valeurs_manquantes": 0.08, "date_future": 0.02,
    "montant_texte": 0.03, "outlier": 0.01, "quantite_negative": 0.01,
    "encodage_nom": 0.02, "paiement_orphelin": 0.01,
}
PRIX_OUTLIER: Final[int] = 99_999_999
COLONNES_BILAN: Final[list[str]] = [
    "defaut", "table", "colonne", "taux_demande", "nb_injecte", "nb_lignes_reference",
]


def resoudre_defauts(defauts: Iterable[str]) -> tuple[str, ...]:
    """Valide les noms, développe « tous » (= les défauts de données) et ordonne."""
    demandes = set(defauts)
    if "tous" in demandes:
        demandes.discard("tous")
        demandes.update(DEFAUTS_DONNEES)
    inconnus = demandes - set(CATALOGUE)
    if inconnus:
        raise ValueError(f"Défaut(s) inconnu(s) {sorted(inconnus)} ; valides : {list(CATALOGUE)}")
    return tuple(d for d in CATALOGUE if d in demandes)


def taux_effectifs(taux: Mapping[str, float] | None) -> dict[str, float]:
    """Taux par défaut, surchargés par ``taux`` ; refuse les noms et valeurs invalides."""
    effectifs = dict(TAUX_PAR_DEFAUT)
    for nom, valeur in (taux or {}).items():
        if nom not in TAUX_PAR_DEFAUT:
            raise ValueError(f"Pas de taux pour {nom!r} ; défauts réglables : {list(TAUX_PAR_DEFAUT)}")
        if not 0.0 <= valeur <= 1.0:
            raise ValueError(f"Taux {nom}={valeur} hors de [0, 1]")
        effectifs[nom] = valeur
    return effectifs


def _rng(graine: int, iso: str, defaut: str) -> np.random.Generator:
    """Un flux aléatoire par défaut, distinct de celui de la vérité ([graine, date])."""
    return np.random.default_rng([graine, int(iso.replace("-", "")), 1, CATALOGUE.index(defaut)])


def _k(taux: float, n: int) -> int:
    return int(round(taux * n))


def _formater_montant(montant: int, variante: int) -> str:
    """« 45 000 FCFA », « 45000 F CFA » ou « 45.000 XOF »."""
    if variante == 0:
        return f"{montant:,}".replace(",", " ") + " FCFA"
    if variante == 1:
        return f"{montant} F CFA"
    return f"{montant:,}".replace(",", ".") + " XOF"


def injecter_defauts(
    tables: Mapping[str, pd.DataFrame],
    run_date: date | str,
    defauts: Iterable[str],
    taux: Mapping[str, float] | None,
    seed: int,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Retourne (tables abîmées, bilan d'injection). Les tables reçues ne sont pas modifiées.

    Les défauts de fichier (``encodage_latin1``, ``colonne_manquante``) sont ignorés ici :
    ils s'appliquent à l'écriture des fichiers.
    """
    iso = normaliser_date(run_date)
    actifs = [d for d in resoudre_defauts(defauts) if d in DEFAUTS_DONNEES]
    t = taux_effectifs(taux)
    out = {nom: df.copy() for nom, df in tables.items()}  # copy() : on ne touche pas l'original
    clients, lignes = out["clients"], out["lignes_commande"]
    commandes, paiements = out["commandes"], out["paiements"]
    n_clients, n_lignes, n_paiements = len(clients), len(lignes), len(paiements)

    lignes["montant_xof"] = lignes["montant_xof"].astype("Int64")  # entier avec « vide » possible
    col = {nom: lignes.columns.get_loc(nom) for nom in lignes.columns}
    libre = np.ones(n_lignes, dtype=bool)  # lignes pas encore touchées par un défaut
    idx_texte = np.array([], dtype=np.int64)
    variantes_texte = np.array([], dtype=np.int64)
    bilan: list[dict[str, object]] = []

    def noter(defaut: str, table: str, colonne: str, nb: int, n_ref: int) -> None:
        bilan.append({"defaut": defaut, "table": table, "colonne": colonne,
                      "taux_demande": t[defaut], "nb_injecte": nb, "nb_lignes_reference": n_ref})

    def tirer(rng: np.random.Generator, pool: np.ndarray, k: int) -> np.ndarray:
        return np.sort(rng.choice(pool, size=min(k, len(pool)), replace=False))

    if "valeurs_manquantes" in actifs:
        rng = _rng(seed, iso, "valeurs_manquantes")
        for nom_col in ("nom_client", "email", "ville"):
            pool = np.flatnonzero(clients[nom_col].notna().to_numpy())
            idx = tirer(rng, pool, _k(t["valeurs_manquantes"], n_clients))
            clients.iloc[idx, clients.columns.get_loc(nom_col)] = None
            noter("valeurs_manquantes", "clients", nom_col, len(idx), n_clients)
            if nom_col == "ville":  # sans ville, la région est inconnue elle aussi
                clients.iloc[idx, clients.columns.get_loc("region")] = None
                noter("valeurs_manquantes", "clients", "region", len(idx), n_clients)
        idx = tirer(rng, np.flatnonzero(libre), _k(t["valeurs_manquantes"], n_lignes))
        lignes.iloc[idx, col["montant_xof"]] = pd.NA
        libre[idx] = False
        noter("valeurs_manquantes", "lignes_commande", "montant_xof", len(idx), n_lignes)

    if "date_future" in actifs:
        rng = _rng(seed, iso, "date_future")
        idx = tirer(rng, np.arange(len(commandes)), _k(t["date_future"], len(commandes)))
        dates = commandes["date_commande"].to_numpy(copy=True)
        decalage = rng.integers(1, 31, len(idx)) * 86_400
        dates[idx] = np.datetime64(iso, "s") + decalage.astype("timedelta64[s]")
        commandes["date_commande"] = dates
        noter("date_future", "commandes", "date_commande", len(idx), len(commandes))

    if "montant_texte" in actifs:
        rng = _rng(seed, iso, "montant_texte")
        idx_texte = tirer(rng, np.flatnonzero(libre), _k(t["montant_texte"], n_lignes))
        variantes_texte = rng.integers(0, 3, len(idx_texte))
        libre[idx_texte] = False
        noter("montant_texte", "lignes_commande", "montant_xof", len(idx_texte), n_lignes)

    if "outlier" in actifs:
        rng = _rng(seed, iso, "outlier")
        idx = tirer(rng, np.flatnonzero(libre), _k(t["outlier"], n_lignes))
        lignes.iloc[idx, col["prix_unitaire_xof"]] = PRIX_OUTLIER
        # Le montant reste cohérent avec quantité × prix : seul le prix est aberrant.
        lignes.iloc[idx, col["montant_xof"]] = lignes["quantite"].to_numpy()[idx] * PRIX_OUTLIER
        libre[idx] = False
        noter("outlier", "lignes_commande", "prix_unitaire_xof", len(idx), n_lignes)

    if "quantite_negative" in actifs:
        rng = _rng(seed, iso, "quantite_negative")
        idx = tirer(rng, np.flatnonzero(libre), _k(t["quantite_negative"], n_lignes))
        valeurs = rng.choice(np.array([0, -1, -2, -3]), size=len(idx))
        lignes.iloc[idx, col["quantite"]] = valeurs
        lignes.iloc[idx, col["montant_xof"]] = valeurs * lignes["prix_unitaire_xof"].to_numpy()[idx]
        libre[idx] = False
        noter("quantite_negative", "lignes_commande", "quantite", len(idx), n_lignes)

    if "encodage_nom" in actifs:
        rng = _rng(seed, iso, "encodage_nom")
        accentue = clients["nom_client"].fillna("").str.contains(r"[^\x00-\x7F]", regex=True)
        idx = tirer(rng, np.flatnonzero(accentue.to_numpy()), _k(t["encodage_nom"], n_clients))
        noms = clients["nom_client"].to_numpy(dtype=object, copy=True)
        for i in idx:  # UTF-8 lu comme Latin-1 : « Aïssatou » devient « AÃ¯ssatou »
            noms[i] = noms[i].encode("utf-8").decode("latin-1")
        clients["nom_client"] = noms
        noter("encodage_nom", "clients", "nom_client", len(idx), n_clients)

    if "paiement_orphelin" in actifs:
        rng = _rng(seed, iso, "paiement_orphelin")
        k = _k(t["paiement_orphelin"], n_paiements)
        orphelins = pd.DataFrame({
            "paiement_id": [f"PAI{n_paiements + j + 1:07d}" for j in range(k)],
            # Numéros au-delà du dernier CMD existant : ces commandes n'existent pas.
            "commande_id": [f"CMD{len(commandes) + j + 1:07d}" for j in range(k)],
            "methode_paiement": rng.choice(METHODES, size=k, p=P_METHODES),
            "statut_paiement": rng.choice(STATUTS_PAIEMENT, size=k, p=P_STATUTS_PAIEMENT),
            "montant_xof": rng.choice(paiements["montant_xof"].to_numpy(), size=k),
            "date_paiement": np.full(k, np.datetime64(iso, "s")),
        })
        paiements = pd.concat([paiements, orphelins], ignore_index=True)
        noter("paiement_orphelin", "paiements", "commande_id", k, n_paiements)

    if len(idx_texte):  # conversion en texte à la fin : elle change le type de la colonne
        montants = lignes["montant_xof"].astype(object)
        for i, variante in zip(idx_texte, variantes_texte, strict=True):
            montants.iat[i] = _formater_montant(int(montants.iat[i]), int(variante))
        lignes["montant_xof"] = montants

    if "doublon_ligne" in actifs:
        rng = _rng(seed, iso, "doublon_ligne")
        # Copies de lignes intactes : la ligne copiée n'a aucun autre défaut.
        idx = tirer(rng, np.flatnonzero(libre), _k(t["doublon_ligne"], n_lignes))
        lignes = pd.concat([lignes, lignes.iloc[idx]], ignore_index=True)
        # Tri stable : la copie suit l'original, donc « garder la première » est bien défini.
        lignes = lignes.sort_values("ligne_commande_id", kind="stable", ignore_index=True)
        noter("doublon_ligne", "lignes_commande", "(ligne entière)", len(idx), n_lignes)

    out["lignes_commande"], out["paiements"] = lignes, paiements
    bilan_df = pd.DataFrame(bilan, columns=COLONNES_BILAN)
    return out, bilan_df
