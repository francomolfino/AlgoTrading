import pandas as pd
import pytest

from algotrading.data.schema import (
    CANONICAL_COLUMNS,
    ValidationError,
    normalize_ohlcv_dataframe,
    validate_ohlcv_dataframe,
)


def test_normalize_ohlcv_dataframe_uses_canonical_columns_and_sorts_dates():
    raw = pd.DataFrame(
        {
            "Date": ["2024-01-03", "2024-01-02"],
            "Open": [102.0, 100.0],
            "High": [103.0, 101.0],
            "Low": [101.0, 99.0],
            "Close": [102.5, 100.5],
            "Adj Close": [102.0, 100.0],
            "Volume": [1_200_000, 1_000_000],
        }
    )

    normalized = normalize_ohlcv_dataframe(raw)

    assert list(normalized.columns) == CANONICAL_COLUMNS
    assert normalized["date"].tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
    assert normalized["close"].tolist() == [100.5, 102.5]


def test_normalize_rejects_empty_frame():
    with pytest.raises(ValidationError, match="vacio"):
        normalize_ohlcv_dataframe(pd.DataFrame())


def test_normalize_fills_adj_close_from_close_when_missing():
    raw = pd.DataFrame(
        {
            "date": ["2024-01-02"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1_000_000],
        }
    )

    normalized = normalize_ohlcv_dataframe(raw)

    assert normalized.loc[0, "adj_close"] == 100.5


def test_validate_raises_when_required_columns_are_missing():
    frame = pd.DataFrame({"date": ["2024-01-02"], "close": [100.0]})

    with pytest.raises(ValidationError, match="open"):
        normalize_ohlcv_dataframe(frame)


def test_validate_raises_when_high_is_below_low():
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": [100.0],
            "high": [98.0],
            "low": [99.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )

    with pytest.raises(ValidationError, match="high menor que low"):
        validate_ohlcv_dataframe(frame)


def test_validate_raises_when_prices_are_not_positive():
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": [100.0],
            "high": [101.0],
            "low": [0.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )

    with pytest.raises(ValidationError, match="precios"):
        validate_ohlcv_dataframe(frame)


def test_validate_raises_when_open_or_close_are_outside_low_high_range():
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": [102.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )

    with pytest.raises(ValidationError, match="open fuera"):
        validate_ohlcv_dataframe(frame)


def test_validate_raises_when_dates_are_invalid_or_duplicated():
    invalid = pd.DataFrame(
        {
            "date": ["not-a-date"],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )
    duplicated = pd.concat([invalid.assign(date="2024-01-02")] * 2, ignore_index=True)

    with pytest.raises(ValidationError, match="fechas invalidas"):
        validate_ohlcv_dataframe(invalid)
    with pytest.raises(ValidationError, match="duplicadas"):
        validate_ohlcv_dataframe(duplicated)


def test_validate_accepts_numeric_strings_without_mutating_input():
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": ["100.0"],
            "high": ["101.0"],
            "low": ["99.0"],
            "close": ["100.5"],
            "adj_close": ["100.5"],
            "volume": ["1000000"],
        }
    )

    validate_ohlcv_dataframe(frame)

    assert frame.loc[0, "open"] == "100.0"


def test_validate_raises_when_numeric_values_are_invalid_or_infinite():
    invalid = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "open": ["bad"],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1_000_000],
        }
    )
    infinite = invalid.assign(open=100.0, close=float("inf"))

    with pytest.raises(ValidationError, match="numericos invalidos"):
        validate_ohlcv_dataframe(invalid)
    with pytest.raises(ValidationError, match="no finitos"):
        validate_ohlcv_dataframe(infinite)
