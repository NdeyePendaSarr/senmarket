"""Génère une partition brute complète : 8 CSV, ``bilan_generation.csv`` et ``senmarket.log``.

Usage (depuis la racine du dépôt, venv actif) ::

    python -m senmarket.generation --run-date 2026-11-05 --rows 10000 --defauts tous
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from senmarket.chemins import charger_env, creer_partition, normaliser_date, partition
from senmarket.defauts import COLONNES_BILAN, injecter_defauts, resoudre_defauts
from senmarket.generateur import generer_verite
from senmarket.journal import configurer_logging

logger = logging.getLogger(__name__)

CLES: Final[dict[str, str]] = {
    "clients": "client_id", "vendeurs": "vendeur_id", "produits": "produit_id",
    "commandes": "commande_id", "lignes_commande": "ligne_commande_id",
    "paiements": "paiement_id", "avis": "avis_id", "navigation": "evenement_id",
}
FICHIER_BILAN: Final[str] = "bilan_generation.csv"
FICHIER_JOURNAL: Final[str] = "senmarket.log"
FICHIERS: Final[tuple[str, ...]] = (
    *(f"{nom}.csv" for nom in CLES), FICHIER_BILAN, FICHIER_JOURNAL,
)
COLONNE_SUPPRIMEE: Final[tuple[str, str]] = ("lignes_commande", "prix_unitaire_xof")
ERREURS_API: Final[tuple[str, ...]] = (
    "échec de connexion à l'API Wave",
    "délai dépassé pour l'API Orange Money",
    "échec de connexion à l'API Wave (nouvelle tentative)",
)


def _graine(seed: int | None) -> int:
    if seed is not None:
        return seed
    charger_env()
    return int(os.environ.get("SENMARKET_SEED", "42"))


def construire_journal(
    tables: Mapping[str, pd.DataFrame],
    bilan: pd.DataFrame,
    run_date: date | str,
    seed: int,
) -> list[str]:
    """Journal d'ingestion simulé ``AAAA-MM-JJ HH:MM:SS NIVEAU ingestion: message``.

    Les nombres viennent de la vraie génération ; les horodatages sont dérivés de
    ``run_date`` et de la graine, jamais de l'heure courante.
    """
    iso = normaliser_date(run_date)
    rng = np.random.default_rng([seed, int(iso.replace("-", "")), 2])
    debut = datetime.fromisoformat(iso) + timedelta(hours=2)
    evenements: list[tuple[int, str, str]] = [(0, "INFO", f"démarrage de l'ingestion {iso}")]

    for i, (nom, df) in enumerate(tables.items()):
        evenements.append((5 + 8 * i, "INFO", f"{nom}: {len(df)} lignes chargées"))
    # La navigation est anonyme par construction : on ne la compte pas parmi les manquants.
    manquantes = sum(int(df.isna().sum().sum()) for nom, df in tables.items() if nom != "navigation")
    evenements.append((80, "WARN", f"{manquantes} valeurs manquantes détectées"))
    anonymes = int(tables["navigation"]["client_id"].isna().sum())
    evenements.append((82, "INFO", f"navigation: {anonymes} événements anonymes (client_id vide)"))

    def nb(defaut: str) -> int:
        sous = bilan.loc[bilan["defaut"] == defaut, "nb_injecte"]
        return int(sous.max()) if len(sous) else 0

    constats = [
        ("doublon_ligne", "{} lignes en double détectées dans lignes_commande"),
        ("date_future", f"{{}} commandes datées après le {iso}"),
        ("montant_texte", "{} montants non numériques dans lignes_commande"),
        ("paiement_orphelin", "{} paiements sans commande correspondante"),
    ]
    for i, (defaut, modele) in enumerate(constats):
        if nb(defaut) > 0:
            evenements.append((84 + 2 * i, "WARN", modele.format(nb(defaut))))
    for _ in range(int(rng.integers(2, 5))):  # quelques erreurs d'API, à des moments variés
        evenements.append((int(rng.integers(10, 900)), "ERROR", str(rng.choice(ERREURS_API))))
    evenements.append((950, "INFO", f"fin de l'ingestion : {len(tables)} tables"))

    evenements.sort(key=lambda e: e[0])  # tri stable : même ordre à chaque exécution
    return [
        f"{(debut + timedelta(seconds=s)):%Y-%m-%d %H:%M:%S} {niveau} ingestion: {message}"
        for s, niveau, message in evenements
    ]


def generer_partition_brute(
    rows: int,
    run_date: date | str,
    jours: int = 365,
    defauts: Sequence[str] = (),
    taux: Mapping[str, float] | None = None,
    seed: int | None = None,
    ecraser: bool = False,
) -> Path:
    """Écrit ``data/raw/date=AAAA-MM-JJ/`` et retourne ce dossier.

    Refuse d'écraser une partition existante sans ``ecraser=True``. On ne supprime
    que les fichiers que ce module crée, jamais le dossier entier.
    """
    iso = normaliser_date(run_date)
    actifs = resoudre_defauts(defauts)  # valide avant d'écrire quoi que ce soit
    dossier = partition("raw", iso)
    existants = [f for f in FICHIERS if (dossier / f).exists()]
    if existants and not ecraser:
        raise FileExistsError(f"La partition {dossier} existe déjà ; relance avec --ecraser")

    graine = _graine(seed)
    logger.info("Génération de la vérité : %d lignes, %d jours, graine %d", rows, jours, graine)
    verite = generer_verite(rows, iso, jours=jours, seed=graine)
    tables, bilan = injecter_defauts(verite, iso, actifs, taux, graine)

    lignes_bilan = bilan.to_dict("records")
    if "encodage_latin1" in actifs:
        lignes_bilan.append({"defaut": "encodage_latin1", "table": "clients",
                             "colonne": "(fichier entier)", "taux_demande": None,
                             "nb_injecte": 1, "nb_lignes_reference": len(tables["clients"])})
    if "colonne_manquante" in actifs:
        table, colonne = COLONNE_SUPPRIMEE
        lignes_bilan.append({"defaut": "colonne_manquante", "table": table, "colonne": colonne,
                             "taux_demande": None, "nb_injecte": 1,
                             "nb_lignes_reference": len(tables[table])})
    bilan = pd.DataFrame(lignes_bilan, columns=COLONNES_BILAN)

    creer_partition("raw", iso)
    for fichier in existants:  # --ecraser : seulement nos propres fichiers
        (dossier / fichier).unlink()
    for nom, df in tables.items():
        sortie = df.sort_values(CLES[nom], kind="stable")  # tri explicite avant écriture
        encodage = "latin-1" if nom == "clients" and "encodage_latin1" in actifs else "utf-8"
        if nom == COLONNE_SUPPRIMEE[0] and "colonne_manquante" in actifs:
            sortie = sortie.drop(columns=[COLONNE_SUPPRIMEE[1]])
        sortie.to_csv(dossier / f"{nom}.csv", index=False, encoding=encodage, lineterminator="\n")
        logger.info("%s.csv : %d lignes", nom, len(sortie))
    bilan.to_csv(dossier / FICHIER_BILAN, index=False, encoding="utf-8", lineterminator="\n")
    journal = construire_journal(tables, bilan, iso, graine)
    (dossier / FICHIER_JOURNAL).write_text("\n".join(journal) + "\n", encoding="utf-8")
    logger.info("Partition brute écrite dans %s", dossier)
    return dossier


def _lire_taux(valeurs: Sequence[str]) -> dict[str, float]:
    """Transforme ``["doublon_ligne=0.1", ...]`` en dictionnaire."""
    taux: dict[str, float] = {}
    for valeur in valeurs:
        nom, sep, nombre = valeur.partition("=")
        if not sep:
            raise ValueError(f"--taux attend nom=valeur, reçu {valeur!r}")
        try:
            taux[nom] = float(nombre)
        except ValueError as exc:
            raise ValueError(f"Taux non numérique : {valeur!r}") from exc
    return taux


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Génère la partition brute SenMarket.")
    parser.add_argument("--run-date", required=True, help="AAAA-MM-JJ")
    parser.add_argument("--rows", type=int, default=10_000, help="lignes de commande")
    parser.add_argument("--jours", type=int, default=365)
    parser.add_argument("--defauts", nargs="*", default=[], help="noms ou « tous »")
    parser.add_argument("--taux", nargs="*", default=[], help="nom=valeur")
    parser.add_argument("--ecraser", action="store_true")
    args = parser.parse_args(argv)

    configurer_logging(args.run_date)
    try:
        generer_partition_brute(
            args.rows, args.run_date, args.jours, args.defauts,
            _lire_taux(args.taux), ecraser=args.ecraser,
        )
    except (ValueError, FileExistsError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
