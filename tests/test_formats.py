"""Tests du chapitre 3 : types conservés et lecture par morceaux."""
from pathlib import Path

import pandas as pd

from senmarket.formats import comparer, lire_par_morceaux


def test_parquet_conserve_les_dates(tmp_path: Path) -> None:
    src = tmp_path / "t.csv"
    pd.DataFrame({"id": [1, 2, 3],
                  "date_commande": ["2026-01-01", "2026-01-02", "2026-01-03"]}
                 ).to_csv(src, index=False)
    mesures = comparer(src, tmp_path / "out", ["date_commande"], "date_commande", 1)
    types = {m.format: m.dtype_colonne for m in mesures}
    assert types["parquet"].startswith("datetime64")
    assert not types["csv"].startswith("datetime64")  # le CSV ne porte pas de type


def test_morceaux_identiques_a_lecture_complete(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    pd.DataFrame({"a": range(10), "b": list("abcdefghij")}).to_csv(p, index=False)
    pd.testing.assert_frame_equal(lire_par_morceaux(p, 3), pd.read_csv(p))
