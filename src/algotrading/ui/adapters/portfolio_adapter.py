from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from algotrading.metrics import calculate_drawdown
from algotrading.portfolio import run_equal_weight_portfolio
from algotrading.portfolio.analysis import build_price_matrix, calculate_return_matrix
from algotrading.ui.adapters.backtest_adapter import minimum_backtest_bars
from algotrading.ui.adapters.data_adapter import filter_by_dates, load_symbol_data, validate_data_quality


@dataclass(frozen=True)
class PortfolioRequest:
    symbols: tuple[str, ...]
    data_dir: Path | str = "data/raw"
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    price_column: str = "adj_close"
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    rebalance_frequency: str = "monthly"
    weighting_mode: str = "equal_weight"
    manual_weights: dict[str, float] | None = None


@dataclass(frozen=True)
class PortfolioUIResult:
    price_matrix: pd.DataFrame
    returns: pd.DataFrame
    portfolio_equity: pd.DataFrame
    portfolio_orders: pd.DataFrame
    correlations: pd.DataFrame
    summary: pd.DataFrame
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioPreflight:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows_by_symbol: dict[str, int]
    aligned_rows: int = 0
    start_date: str = "n/a"
    end_date: str = "n/a"

    @property
    def can_run(self) -> bool:
        return not self.errors


def run_portfolio_request(request: PortfolioRequest) -> PortfolioUIResult:
    warnings = validate_portfolio_request(request)
    frames = _load_frames(request)
    if request.weighting_mode == "equal_weight":
        result = run_equal_weight_portfolio(
            frames=frames,
            initial_capital=request.initial_capital,
            price_column=request.price_column,
            rebalance_frequency=request.rebalance_frequency,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
        )
        return PortfolioUIResult(
            price_matrix=result.price_matrix,
            returns=result.return_matrix,
            portfolio_equity=result.portfolio_equity,
            portfolio_orders=result.portfolio_orders,
            correlations=result.correlations,
            summary=result.summary,
            warnings=tuple(warnings),
        )

    return _run_manual_weight_portfolio(request, frames, warnings)


def preflight_portfolio_request(request: PortfolioRequest) -> PortfolioPreflight:
    errors: list[str] = []
    warnings: list[str] = []
    rows_by_symbol: dict[str, int] = {}

    try:
        warnings.extend(validate_portfolio_request(request))
    except ValueError as exc:
        errors.append(str(exc))
        return PortfolioPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows_by_symbol=rows_by_symbol,
        )

    frames: dict[str, pd.DataFrame] = {}
    minimum_bars = minimum_backtest_bars(request.interval)
    for symbol in request.symbols:
        try:
            frame, _ = load_symbol_data(request.data_dir, symbol, request.interval)
            frame = filter_by_dates(frame, request.start, request.end)
        except Exception as exc:
            errors.append(f"{symbol}: no pude cargar datos: {exc}")
            continue

        rows_by_symbol[symbol] = int(len(frame))
        if len(frame) < minimum_bars:
            errors.append(
                f"{symbol}: periodo demasiado corto ({len(frame)} barras). Para {request.interval} usa al menos {minimum_bars}."
            )
        quality = validate_data_quality(frame)
        if not quality.is_valid:
            errors.append(f"{symbol}: datos invalidos: {quality.message}")
        frames[symbol] = frame

    if errors:
        return PortfolioPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows_by_symbol=rows_by_symbol,
        )

    try:
        prices = build_price_matrix(frames, price_column=request.price_column)
    except Exception as exc:
        errors.append(f"No pude alinear precios del portfolio: {exc}")
        return PortfolioPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows_by_symbol=rows_by_symbol,
        )

    aligned_rows = int(len(prices))
    start_date = prices.index[0].strftime("%Y-%m-%d")
    end_date = prices.index[-1].strftime("%Y-%m-%d")
    if aligned_rows < minimum_bars:
        errors.append(
            f"Fechas comunes insuficientes: {aligned_rows} barras alineadas. Para {request.interval} usa al menos {minimum_bars}."
        )
    max_rows = max(rows_by_symbol.values(), default=0)
    if max_rows and aligned_rows < max_rows * 0.75:
        warnings.append("Se pierden muchas filas al alinear activos; revisa rangos de fechas y disponibilidad.")
    if request.commission_bps == 0 and request.slippage_bps == 0:
        warnings.append("Comision y slippage estan en cero; el portfolio puede verse mejor de lo realista.")

    return PortfolioPreflight(
        errors=tuple(errors),
        warnings=tuple(warnings),
        rows_by_symbol=rows_by_symbol,
        aligned_rows=aligned_rows,
        start_date=start_date,
        end_date=end_date,
    )


def validate_portfolio_request(request: PortfolioRequest) -> list[str]:
    if len(request.symbols) < 2:
        raise ValueError("Selecciona al menos dos activos.")
    if request.initial_capital <= 0:
        raise ValueError("El capital inicial debe ser mayor a cero.")
    if request.commission_bps < 0 or request.slippage_bps < 0:
        raise ValueError("Comision y slippage no pueden ser negativos.")
    if request.weighting_mode not in {"equal_weight", "manual"}:
        raise ValueError("Modo de pesos no soportado.")

    warnings: list[str] = []
    if request.weighting_mode == "manual":
        weights = request.manual_weights or {}
        missing = [symbol for symbol in request.symbols if symbol not in weights]
        if missing:
            raise ValueError(f"Faltan pesos para: {', '.join(missing)}")
        total = sum(float(weights[symbol]) for symbol in request.symbols)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("Los pesos manuales deben sumar 100%.")
        if max(weights.values()) > 0.8:
            raise ValueError("Un peso manual supera 80%; eso es demasiada concentracion para esta UI educativa.")
        if max(weights.values()) > 0.6:
            warnings.append("Hay demasiada concentracion en un solo activo.")
        warnings.append("Pesos manuales usan simulacion estatica sin ordenes de rebalanceo detalladas.")
    return warnings


def _load_frames(request: PortfolioRequest) -> dict[str, pd.DataFrame]:
    frames = {}
    for symbol in request.symbols:
        frame, _ = load_symbol_data(request.data_dir, symbol, request.interval)
        frames[symbol] = filter_by_dates(frame, request.start, request.end)
    return frames


def _run_manual_weight_portfolio(
    request: PortfolioRequest,
    frames: dict[str, pd.DataFrame],
    warnings: list[str],
) -> PortfolioUIResult:
    weights = pd.Series(request.manual_weights or {}, dtype=float)
    prices = build_price_matrix(frames, price_column=request.price_column)
    returns = calculate_return_matrix(prices)
    portfolio_returns = returns.mul(weights[returns.columns], axis=1).sum(axis=1)
    equity = request.initial_capital * (1 + portfolio_returns).cumprod()
    equity = pd.concat(
        [
            pd.Series([request.initial_capital], index=[prices.index[0]]),
            equity,
        ]
    )
    equity = equity[~equity.index.duplicated(keep="last")]
    portfolio_equity = pd.DataFrame(
        {
            "date": equity.index,
            "equity": equity.values,
            "daily_return": equity.pct_change(fill_method=None).fillna(0.0).values,
        }
    )
    portfolio_equity["drawdown"] = calculate_drawdown(portfolio_equity["equity"])
    for symbol in request.symbols:
        portfolio_equity[f"weight_{symbol}"] = float(weights[symbol])

    summary = pd.DataFrame(
        [
            {
                "name": "manual_weight_portfolio",
                "kind": "portfolio",
                "start_date": portfolio_equity["date"].iloc[0].strftime("%Y-%m-%d"),
                "end_date": portfolio_equity["date"].iloc[-1].strftime("%Y-%m-%d"),
                "rows": len(portfolio_equity),
                "final_equity": float(portfolio_equity["equity"].iloc[-1]),
                "total_return": float(portfolio_equity["equity"].iloc[-1] / request.initial_capital - 1),
                "max_drawdown": float(portfolio_equity["drawdown"].min()),
            }
        ]
    )
    return PortfolioUIResult(
        price_matrix=prices,
        returns=returns,
        portfolio_equity=portfolio_equity,
        portfolio_orders=pd.DataFrame(),
        correlations=returns.corr(),
        summary=summary,
        warnings=tuple(warnings),
    )
