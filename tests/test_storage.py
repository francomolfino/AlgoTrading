from pathlib import Path

import pandas as pd
import pytest

from algotrading.data.schema import ValidationError
from algotrading.data.storage import (
    build_data_path,
    load_ohlcv,
    safe_filename_part,
    save_ohlcv,
)


def test_safe_filename_part_handles_crypto_symbols():
    assert safe_filename_part("BTC-USD") == "BTC_USD"


def test_build_data_path_uses_symbol_interval_and_format():
    path = build_data_path(Path("tests/.tmp"), "SPY", "1d", "csv")

    assert path.name == "SPY_1D.csv"


def test_save_and_load_csv_roundtrip():
    frame = _valid_frame()
    path = Path("tests/.tmp/SPY_1d.csv")

    save_ohlcv(frame, path)
    loaded = load_ohlcv(path)

    assert len(loaded) == 2
    assert list(loaded.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    ]


def test_save_and_load_parquet_roundtrip():
    frame = _valid_frame()
    path = Path("tests/.tmp/SPY_1d.parquet")

    save_ohlcv(frame, path)
    loaded = load_ohlcv(path)

    assert len(loaded) == 2
    assert loaded["close"].tolist() == [100.5, 101.5]


def test_load_ohlcv_rejects_invalid_persisted_csv():
    frame = _valid_frame().astype({"close": "object"})
    frame.loc[1, "close"] = "not-a-number"
    path = Path("tests/.tmp/invalid.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)

    with pytest.raises(ValidationError, match="numericos invalidos"):
        load_ohlcv(path)


def _valid_frame():
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "adj_close": [100.5, 101.5],
            "volume": [1_000_000, 1_200_000],
        }
    )
