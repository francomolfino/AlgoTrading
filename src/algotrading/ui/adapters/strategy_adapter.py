from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from algotrading.strategies.breakout import generate_breakout_signals
from algotrading.strategies.buy_and_hold import generate_buy_and_hold_signals
from algotrading.strategies.moving_average import generate_sma_crossover_signals
from algotrading.strategies.rsi import generate_rsi_signals
from algotrading.strategies.trend_filter import generate_trend_filter_signals

ParameterKind = Literal["int", "float"]


@dataclass(frozen=True)
class StrategyParameter:
    name: str
    label: str
    kind: ParameterKind
    default: int | float
    minimum: int | float
    maximum: int | float
    step: int | float
    help: str


@dataclass(frozen=True)
class StrategyUIConfig:
    key: str
    label: str
    description: str
    risk_note: str
    parameters: tuple[StrategyParameter, ...]
    function: Callable[..., pd.DataFrame]


STRATEGIES: dict[str, StrategyUIConfig] = {
    "buy_and_hold": StrategyUIConfig(
        key="buy_and_hold",
        label="Buy and hold",
        description="Compra y mantiene. Es el benchmark minimo que toda estrategia deberia mirar.",
        risk_note="Puede tener drawdowns profundos porque siempre esta expuesta.",
        parameters=(),
        function=generate_buy_and_hold_signals,
    ),
    "sma_cross": StrategyUIConfig(
        key="sma_cross",
        label="Cruce de medias moviles",
        description="Long cuando la media rapida supera a la media lenta.",
        risk_note="Llega tarde por construccion y puede sufrir en mercados laterales.",
        parameters=(
            StrategyParameter(
                "fast_window",
                "Media rapida",
                "int",
                50,
                2,
                300,
                1,
                "Ventana corta. Debe ser menor que la media lenta.",
            ),
            StrategyParameter(
                "slow_window",
                "Media lenta",
                "int",
                200,
                5,
                500,
                1,
                "Ventana larga usada como tendencia de referencia.",
            ),
        ),
        function=generate_sma_crossover_signals,
    ),
    "rsi": StrategyUIConfig(
        key="rsi",
        label="RSI basico",
        description="Entra cuando RSI cae bajo sobreventa y sale al superar sobrecompra.",
        risk_note="Puede comprar activos que siguen cayendo; no es una garantia de rebote.",
        parameters=(
            StrategyParameter("window", "Ventana RSI", "int", 14, 2, 100, 1, "Barras usadas para calcular RSI."),
            StrategyParameter("oversold", "Sobreventa", "float", 30.0, 1.0, 60.0, 1.0, "Umbral de entrada."),
            StrategyParameter("overbought", "Sobrecompra", "float", 70.0, 40.0, 99.0, 1.0, "Umbral de salida."),
        ),
        function=generate_rsi_signals,
    ),
    "breakout": StrategyUIConfig(
        key="breakout",
        label="Breakout simple",
        description="Entra al superar maximos previos y sale al perder minimos previos.",
        risk_note="Puede encadenar falsas rupturas si el mercado esta lateral.",
        parameters=(
            StrategyParameter("entry_window", "Ventana entrada", "int", 55, 2, 300, 1, "Maximo previo a superar."),
            StrategyParameter("exit_window", "Ventana salida", "int", 20, 2, 300, 1, "Minimo previo que dispara salida."),
        ),
        function=generate_breakout_signals,
    ),
    "trend_filter": StrategyUIConfig(
        key="trend_filter",
        label="Cruce con filtro de tendencia",
        description="Cruce de medias habilitado solo cuando el precio supera una media larga.",
        risk_note="Reduce operaciones contra tendencia, pero puede quedar fuera de rebotes rapidos.",
        parameters=(
            StrategyParameter("fast_window", "Media rapida", "int", 20, 2, 300, 1, "Ventana corta del cruce."),
            StrategyParameter("slow_window", "Media lenta", "int", 100, 5, 500, 1, "Ventana larga del cruce."),
            StrategyParameter("trend_window", "Filtro tendencia", "int", 200, 10, 600, 1, "Media larga para habilitar entradas."),
        ),
        function=generate_trend_filter_signals,
    ),
}


def list_strategy_configs() -> list[StrategyUIConfig]:
    return list(STRATEGIES.values())


def get_strategy_config(strategy_key: str) -> StrategyUIConfig:
    try:
        return STRATEGIES[strategy_key]
    except KeyError as exc:
        raise ValueError(f"Estrategia no soportada: {strategy_key}") from exc


def default_parameters(strategy_key: str) -> dict[str, int | float]:
    return {parameter.name: parameter.default for parameter in get_strategy_config(strategy_key).parameters}


def validate_strategy_parameters(
    strategy_key: str,
    parameters: dict[str, int | float],
    frame_length: int | None = None,
) -> list[str]:
    config = get_strategy_config(strategy_key)
    warnings: list[str] = []
    expected = {parameter.name: parameter for parameter in config.parameters}
    unknown = sorted(set(parameters) - set(expected))
    if unknown:
        raise ValueError(f"Parametros desconocidos para {config.label}: {', '.join(unknown)}")

    for name, parameter in expected.items():
        if name not in parameters:
            raise ValueError(f"Falta parametro: {name}")
        value = parameters[name]
        if value < parameter.minimum or value > parameter.maximum:
            raise ValueError(f"{parameter.label} debe estar entre {parameter.minimum} y {parameter.maximum}.")

    if strategy_key in {"sma_cross", "trend_filter"}:
        fast = int(parameters["fast_window"])
        slow = int(parameters["slow_window"])
        if fast >= slow:
            raise ValueError("La media rapida debe ser menor que la media lenta.")
        if slow / fast > 20:
            warnings.append("Las ventanas estan muy separadas; la estrategia puede reaccionar demasiado tarde.")

    if strategy_key == "trend_filter":
        trend = int(parameters["trend_window"])
        slow = int(parameters["slow_window"])
        if trend < slow:
            warnings.append("El filtro de tendencia es menor que la media lenta; revisa si tiene sentido.")

    if strategy_key == "rsi":
        oversold = float(parameters["oversold"])
        overbought = float(parameters["overbought"])
        if oversold >= overbought:
            raise ValueError("Sobreventa debe ser menor que sobrecompra.")
        if overbought - oversold < 15:
            warnings.append("Los umbrales RSI estan muy cerca; puede generar mucho ruido.")

    if frame_length is not None:
        max_window = _max_window(strategy_key, parameters)
        if max_window and frame_length < max_window * 2:
            warnings.append("Hay pocos datos para ventanas tan largas; las metricas pueden ser fragiles.")

    return warnings


def generate_strategy_signals(
    frame: pd.DataFrame,
    strategy_key: str,
    parameters: dict[str, int | float] | None = None,
    price_column: str = "adj_close",
    signal_column: str = "signal",
) -> pd.DataFrame:
    parameters = parameters or default_parameters(strategy_key)
    validate_strategy_parameters(strategy_key, parameters, frame_length=len(frame))
    config = get_strategy_config(strategy_key)
    kwargs = dict(parameters)
    if strategy_key not in {"buy_and_hold"}:
        kwargs["price_column"] = price_column
    kwargs["signal_column"] = signal_column
    return config.function(frame, **kwargs)


def signal_summary(frame: pd.DataFrame, signal_column: str = "signal") -> dict[str, int | float]:
    if signal_column not in frame:
        raise ValueError(f"Falta columna de senal: {signal_column}")
    signal = pd.to_numeric(frame[signal_column], errors="coerce").fillna(0).astype(int)
    previous = signal.shift(1).fillna(0).astype(int)
    entries = int(((signal == 1) & (previous == 0)).sum())
    exits = int(((signal == 0) & (previous == 1)).sum())
    exposure = float((signal == 1).mean()) if len(signal) else 0.0
    return {
        "entries": entries,
        "exits": exits,
        "bars_in_market": int((signal == 1).sum()),
        "exposure_ratio": exposure,
    }


def signal_events_frame(
    frame: pd.DataFrame,
    signal_column: str = "signal",
    price_column: str = "adj_close",
) -> pd.DataFrame:
    if signal_column not in frame:
        raise ValueError(f"Falta columna de senal: {signal_column}")

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce") if "date" in data else pd.NaT
    signal = pd.to_numeric(data[signal_column], errors="coerce").fillna(0).astype(int)
    previous = signal.shift(1).fillna(0).astype(int)
    changed = signal.ne(previous)
    events = data.loc[changed].copy()
    if events.empty:
        return pd.DataFrame(columns=["date", "event", "signal", "previous_signal", "price"])

    event_signal = signal.loc[events.index]
    previous_signal = previous.loc[events.index]
    price_source = price_column if price_column in events.columns else "close" if "close" in events.columns else None
    price = pd.to_numeric(events[price_source], errors="coerce") if price_source else pd.Series(index=events.index, dtype=float)
    result = pd.DataFrame(
        {
            "date": events["date"].dt.strftime("%Y-%m-%d"),
            "event": event_signal.map({1: "entrada", 0: "salida"}).fillna("cambio"),
            "signal": event_signal.astype(int),
            "previous_signal": previous_signal.astype(int),
            "price": price,
        }
    )
    extra_columns = [
        column
        for column in events.columns
        if column.startswith(("sma_", "rolling_high_", "rolling_low_")) or column == "rsi"
    ]
    for column in extra_columns[:5]:
        result[column] = pd.to_numeric(events[column], errors="coerce")
    return result.reset_index(drop=True)


def strategy_display_name(strategy_key: str, parameters: dict[str, int | float]) -> str:
    if strategy_key == "buy_and_hold":
        return "buy_and_hold"
    suffix = "_".join(str(int(value)) if float(value).is_integer() else str(value) for value in parameters.values())
    return f"{strategy_key}_{suffix}"


def _max_window(strategy_key: str, parameters: dict[str, int | float]) -> int:
    if strategy_key == "buy_and_hold":
        return 0
    window_keys = [key for key in parameters if "window" in key]
    return max([int(parameters[key]) for key in window_keys], default=0)
