"""Chapitre 3 (ticket SM-004) : comparer CSV, JSON, JSON Lines et Parquet."""
from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

FORMATS: tuple[str, ...] = ("csv", "json", "jsonl", "parquet")

# Un lecteur par format, avec les réglages PAR DÉFAUT de Pandas :
# on veut voir ce que Pandas infère tout seul (question 1 du chapitre).
LECTEURS: dict[str, Callable[[Path], pd.DataFrame]] = {
    "csv": lambda p: pd.read_csv(p),
    "json": lambda p: pd.read_json(p, orient="records"),
    "jsonl": lambda p: pd.read_json(p, orient="records", lines=True),
    "parquet": lambda p: pd.read_parquet(p),
}


@dataclass(frozen=True)
class Mesure:
    """Résultat pour un format."""

    format: str
    mediane_s: float
    taille_mo: float
    dtype_colonne: str  # type Pandas de la colonne choisie, relu depuis le fichier


def exporter(df: pd.DataFrame, dossier: Path, base: str) -> dict[str, Path]:
    """Écrit le même DataFrame dans les 4 formats et renvoie les chemins."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = {f: dossier / f"{base}.{f}" for f in FORMATS}
    df.to_csv(chemins["csv"], index=False)
    # date_format="iso" : sinon les dates sont écrites en millisecondes depuis 1970.
    df.to_json(chemins["json"], orient="records", date_format="iso", force_ascii=False)
    df.to_json(chemins["jsonl"], orient="records", lines=True,
               date_format="iso", force_ascii=False)
    df.to_parquet(chemins["parquet"], index=False)  # nécessite pyarrow
    return chemins


def mesurer_lecture(lecteur: Callable[[Path], pd.DataFrame], chemin: Path,
                    repetitions: int = 5) -> float:
    """Médiane (en secondes) de `repetitions` lectures, la 1re lecture étant ignorée."""
    lecteur(chemin)  # lecture de chauffe, non comptée
    durees: list[float] = []
    for _ in range(repetitions):
        debut = time.perf_counter()
        lecteur(chemin)
        durees.append(time.perf_counter() - debut)
    return statistics.median(durees)


def comparer(source: Path, dossier: Path, dates: list[str], colonne: str | None = None,
             repetitions: int = 5) -> list[Mesure]:
    """Exporte `source` (un CSV) dans les 4 formats et mesure chacun."""
    df = pd.read_csv(source, parse_dates=dates)
    chemins = exporter(df, dossier, source.stem)
    col = colonne or str(df.columns[0])
    mesures: list[Mesure] = []
    for f in FORMATS:
        mesures.append(Mesure(
            format=f,
            mediane_s=mesurer_lecture(LECTEURS[f], chemins[f], repetitions),
            taille_mo=chemins[f].stat().st_size / 1_048_576,
            dtype_colonne=str(LECTEURS[f](chemins[f])[col].dtype),
        ))
    return mesures


def lire_par_morceaux(chemin: Path, lignes_par_morceau: int = 50_000,
                      dates: list[str] | None = None) -> pd.DataFrame:
    """Lit un CSV par morceaux puis les réassemble."""
    morceaux = pd.read_csv(chemin, chunksize=lignes_par_morceau, parse_dates=dates or [])
    return pd.concat(morceaux, ignore_index=True)


def en_markdown(mesures: list[Mesure], colonne: str) -> str:
    """Tableau prêt à coller dans docs/MESURES.md."""
    lignes = [f"| format | temps médian (s) | taille (Mo) | type de `{colonne}` |",
              "|---|---|---|---|"]
    lignes += [f"| {m.format} | {m.mediane_s:.3f} | {m.taille_mo:.1f} | {m.dtype_colonne} |"
               for m in mesures]
    return "\n".join(lignes)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="CSV à comparer")
    p.add_argument("--dates", nargs="*", default=[], help="colonnes à parser en dates")
    p.add_argument("--colonne", default=None, help="colonne dont on affiche le type")
    p.add_argument("--sortie", type=Path, default=Path("data/formats"))
    a = p.parse_args()

    mesures = comparer(a.source, a.sortie, a.dates, a.colonne)
    print(en_markdown(mesures, a.colonne or "1re colonne"))

    # Lecture par morceaux : doit être identique à la lecture complète.
    try:
        pd.testing.assert_frame_equal(
            lire_par_morceaux(a.source, dates=a.dates),
            pd.read_csv(a.source, parse_dates=a.dates))
        print("\nchunksize : identique à la lecture complète")
    except AssertionError as e:
        print(f"\nchunksize : DIFFÉRENT -> {e}")


if __name__ == "__main__":
    main()
