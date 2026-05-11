from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from algotrading.backtesting.engine import BacktestConfig, run_backtest


@dataclass(frozen=True)
class CorrectnessCheck:
    name: str
    category: str
    passed: bool
    detail: str
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class BacktestCorrectnessAuditResult:
    passed: bool
    report_path: Path
    checks: tuple[CorrectnessCheck, ...]
    limitations: tuple[str, ...] = field(default_factory=tuple)


def run_backtest_correctness_audit(
    report_path: Path | str = "reports/backtest_correctness_audit.md",
) -> BacktestCorrectnessAuditResult:
    """Ejecuta golden tests calculables a mano y genera un reporte auditable."""
    checks: list[CorrectnessCheck] = []
    for check in _CHECKS:
        try:
            checks.append(check())
        except Exception as exc:
            checks.append(
                CorrectnessCheck(
                    name=check.__name__.removeprefix("_check_").replace("_", " "),
                    category="fallo no controlado",
                    passed=False,
                    detail=str(exc),
                )
            )

    result = BacktestCorrectnessAuditResult(
        passed=all(check.passed for check in checks),
        report_path=Path(report_path),
        checks=tuple(checks),
        limitations=_known_limitations(),
    )
    _write_report(result)
    return result


def _check_flat_price_no_trades() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 100, 100, 100], [0, 0, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    passed = (
        result.orders.empty
        and result.trades.empty
        and result.metrics["final_equity"] == 1_000
        and result.metrics["total_return"] == 0
        and result.metrics["max_drawdown"] == 0
        and result.equity_curve["equity"].eq(1_000).all()
    )
    return CorrectnessCheck(
        name="Precio plano sin trades",
        category="cash/equity/drawdown",
        passed=passed,
        detail=(
            f"equity_final={result.metrics['final_equity']:.2f}, "
            f"trades={result.metrics['number_of_trades']}, "
            f"max_drawdown={result.metrics['max_drawdown']:.4f}"
        ),
        assumptions=("Sin senales, el capital debe permanecer en cash.",),
    )


def _check_rising_buy_and_hold_exact_return() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 110, 120, 130], [1, 1, 1, 1]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    expected_final = 1_000 * 130 / 110
    passed = (
        _near(result.metrics["final_equity"], expected_final)
        and _near(result.metrics["benchmark_final_equity"], expected_final)
        and result.orders["side"].tolist() == ["buy", "sell"]
        and result.trades.loc[0, "entry_date"] == pd.Timestamp("2024-01-02")
        and result.trades.loc[0, "exit_date"] == pd.Timestamp("2024-01-04")
    )
    return CorrectnessCheck(
        name="Buy and hold con precio ascendente",
        category="retorno/benchmark",
        passed=passed,
        detail=(
            f"esperado={expected_final:.6f}, "
            f"equity_final={result.metrics['final_equity']:.6f}, "
            f"benchmark={result.metrics['benchmark_final_equity']:.6f}"
        ),
        assumptions=(
            "La entrada ocurre en la barra posterior a la primera senal.",
            "El cierre forzado final liquida la posicion en la ultima barra.",
        ),
    )


def _check_one_trade_costs_and_slippage_exact_pnl() -> CorrectnessCheck:
    initial_capital = 1_000.0
    commission_bps = 100.0
    slippage_bps = 100.0
    commission_rate = commission_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    entry_mark = 100.0
    exit_mark = 110.0
    entry_execution = entry_mark * (1 + slippage_rate)
    exit_execution = exit_mark * (1 - slippage_rate)
    entry_notional = initial_capital / (1 + commission_rate)
    entry_commission = entry_notional * commission_rate
    shares = entry_notional / entry_execution
    exit_notional = shares * exit_execution
    exit_commission = exit_notional * commission_rate
    expected_final = exit_notional - exit_commission
    expected_pnl = expected_final - initial_capital

    result = run_backtest(
        _frame([100, 100, 110, 110], [1, 1, 0, 0]),
        BacktestConfig(
            initial_capital=initial_capital,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
        ),
    )

    trade = result.trades.loc[0]
    orders = result.orders
    passed = (
        _near(result.metrics["final_equity"], expected_final)
        and _near(trade["pnl"], expected_pnl)
        and _near(trade["entry_price"], entry_execution)
        and _near(trade["exit_price"], exit_execution)
        and _near(orders.loc[0, "commission"], entry_commission)
        and _near(orders.loc[1, "commission"], exit_commission)
    )
    return CorrectnessCheck(
        name="Una compra y una venta con costos exactos",
        category="comisiones/slippage/pnl",
        passed=passed,
        detail=(
            f"final_esperado={expected_final:.6f}, "
            f"final_obtenido={result.metrics['final_equity']:.6f}, "
            f"pnl_esperado={expected_pnl:.6f}, pnl_obtenido={trade['pnl']:.6f}"
        ),
        assumptions=(
            "El slippage empeora compra y venta.",
            "La comision se cobra en entrada y salida.",
        ),
    )


def _check_signal_executes_next_bar() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 150, 90, 90], [0, 1, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    passed = (
        result.equity_curve.loc[1, "action"] == ""
        and result.equity_curve.loc[2, "action"] == "buy"
        and result.trades.loc[0, "entry_price"] == 90
        and result.trades.loc[0, "entry_date"] == pd.Timestamp("2024-01-03")
    )
    return CorrectnessCheck(
        name="Senal en t ejecuta en t+1",
        category="lookahead bias",
        passed=passed,
        detail=(
            f"accion_t={result.equity_curve.loc[1, 'action'] or 'sin accion'}, "
            f"accion_t_plus_1={result.equity_curve.loc[2, 'action']}, "
            f"entry_price={result.trades.loc[0, 'entry_price']:.2f}"
        ),
        assumptions=("El backtester no compra al cierre de la misma barra que genero la senal.",),
    )


def _check_missing_signal_handling() -> CorrectnessCheck:
    default_rejected = False
    try:
        run_backtest(_frame([100, 101, 102], [0, None, 0]))
    except ValueError as exc:
        default_rejected = "senales faltantes" in str(exc)

    explicit_cash = run_backtest(
        _frame([100, 101, 102], [0, None, 0]),
        BacktestConfig(
            initial_capital=1_000,
            commission_bps=0,
            slippage_bps=0,
            allow_missing_signals=True,
        ),
    )
    passed = default_rejected and explicit_cash.orders.empty and explicit_cash.metrics["final_equity"] == 1_000
    return CorrectnessCheck(
        name="Senales NaN no operan accidentalmente",
        category="validacion de datos",
        passed=passed,
        detail=(
            f"rechazo_default={default_rejected}, "
            f"ordenes_con_cash_explicito={len(explicit_cash.orders)}"
        ),
        assumptions=(
            "Por defecto una senal faltante invalida el backtest.",
            "Si se habilita explicitamente, NaN se trata como cash.",
        ),
    )


def _check_duplicate_dates_rejected() -> CorrectnessCheck:
    frame = _frame([100, 101, 102], [0, 1, 0])
    frame.loc[2, "date"] = frame.loc[1, "date"]
    rejected = False
    try:
        run_backtest(frame)
    except ValueError as exc:
        rejected = "duplicadas" in str(exc)
    return CorrectnessCheck(
        name="Fechas duplicadas rechazadas",
        category="validacion de datos",
        passed=rejected,
        detail=f"rechazado={rejected}",
        assumptions=("Una fecha duplicada puede duplicar operaciones o distorsionar retornos.",),
    )


def _check_gap_stop_loss_rule() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 100, 70, 80], [1, 1, 1, 1]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0, stop_loss_pct=0.10),
    )
    passed = (
        result.trades.loc[0, "exit_reason"] == "stop_loss"
        and result.trades.loc[0, "exit_date"] == pd.Timestamp("2024-01-03")
        and result.metrics["final_equity"] == 700
    )
    return CorrectnessCheck(
        name="Gap contra stop loss",
        category="risk management",
        passed=passed,
        detail=(
            f"exit_reason={result.trades.loc[0, 'exit_reason']}, "
            f"exit_price={result.trades.loc[0, 'exit_price']:.2f}, "
            f"equity_final={result.metrics['final_equity']:.2f}"
        ),
        assumptions=(
            "El stop loss se evalua con el precio de cierre disponible.",
            "Si el precio abre/salta por debajo del stop, se sale al precio observado de la barra.",
        ),
    )


def _check_insufficient_capital_is_sized_to_cash() -> CorrectnessCheck:
    result = run_backtest(
        _frame([10_000, 10_000, 12_000], [1, 1, 1]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    buy_order = result.orders.loc[0]
    passed = (
        _near(buy_order["filled_shares"], 0.1)
        and result.equity_curve["cash"].min() >= -1e-9
        and result.equity_curve["shares"].min() >= 0
        and result.orders["status"].eq("filled").all()
    )
    return CorrectnessCheck(
        name="Capital menor al precio del activo",
        category="cash/position sizing",
        passed=passed,
        detail=(
            f"shares={buy_order['filled_shares']:.6f}, "
            f"cash_min={result.equity_curve['cash'].min():.6f}, "
            f"final={result.metrics['final_equity']:.2f}"
        ),
        assumptions=(
            "El backtester permite acciones fraccionarias.",
            "La orden se dimensiona al cash disponible; no hay margen ni cash negativo.",
        ),
    )


def _check_equity_accounting_and_drawdown() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 100, 80, 120, 90], [1, 1, 1, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    equity_curve = result.equity_curve
    accounting = equity_curve["cash"] + equity_curve["shares"] * equity_curve["price"]
    expected_drawdown = equity_curve["equity"] / equity_curve["equity"].cummax() - 1
    passed = (
        _series_near(equity_curve["equity"], accounting)
        and _series_near(equity_curve["drawdown"], expected_drawdown)
        and equity_curve["position"].isin([0, 1]).all()
        and (equity_curve["shares"] >= 0).all()
    )
    return CorrectnessCheck(
        name="Equity, drawdown y posicion long-only",
        category="equity/drawdown/posiciones",
        passed=passed,
        detail=(
            f"max_drawdown={result.metrics['max_drawdown']:.4f}, "
            f"posiciones={sorted(equity_curve['position'].unique().tolist())}"
        ),
        assumptions=(
            "Equity se calcula como cash + shares * precio observado.",
            "Drawdown se calcula contra maximos acumulados.",
            "No se permiten posiciones short.",
        ),
    )


def _check_benchmark_period_alignment() -> CorrectnessCheck:
    result = run_backtest(
        _frame([100, 105, 95, 110, 115], [0, 0, 0, 0, 0]),
        BacktestConfig(initial_capital=1_000, commission_bps=0, slippage_bps=0),
    )
    equity = result.equity_curve
    passed = (
        len(equity["benchmark_equity"]) == len(equity)
        and equity["benchmark_equity"].notna().all()
        and equity["benchmark_drawdown"].notna().all()
        and _near(equity["benchmark_equity"].iloc[0], result.config.initial_capital)
        and "benchmark_total_return" in result.metrics
    )
    return CorrectnessCheck(
        name="Benchmark alineado al mismo periodo",
        category="benchmark",
        passed=passed,
        detail=(
            f"filas_equity={len(equity)}, "
            f"filas_benchmark={len(equity['benchmark_equity'])}, "
            f"benchmark_return={result.metrics['benchmark_total_return']:.4f}"
        ),
        assumptions=("La comparacion contra benchmark usa las mismas fechas que la estrategia.",),
    )


def _frame(prices: list[float], signals: list[float | int | None]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "adj_close": prices,
            "signal": signals,
        }
    )


def _near(left: float, right: float, tolerance: float = 1e-8) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def _series_near(left: pd.Series, right: pd.Series, tolerance: float = 1e-8) -> bool:
    diff = (pd.to_numeric(left) - pd.to_numeric(right)).abs()
    return bool((diff <= tolerance).all())


def _known_limitations() -> tuple[str, ...]:
    return (
        "No modela liquidez real, spreads variables, impacto de mercado ni fills parciales.",
        "Permite acciones fraccionarias; no valida lotes minimos ni restricciones de broker.",
        "Stop loss y take profit usan el precio de cierre de la barra simulada, no precios intradiarios.",
        "No modela impuestos, borrow fees, dividendos separados ni corporate actions mas alla del precio ajustado recibido.",
        "El benchmark buy and hold usa la misma regla de ejecucion t+1 y los mismos costos configurados.",
    )


def _write_report(result: BacktestCorrectnessAuditResult) -> None:
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if result.passed else "FAIL"
    lines = [
        "# Backtest Correctness Audit",
        "",
        f"- Fecha UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"- Estado: **{status}**",
        f"- Checks ejecutados: {len(result.checks)}",
        "",
        "## Resultado de checks",
        "",
    ]
    for check in result.checks:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(f"- **{mark}** - {check.name} ({check.category}): {check.detail}")
        for assumption in check.assumptions:
            lines.append(f"  - Supuesto validado: {assumption}")

    lines.extend(["", "## Limitaciones conocidas", ""])
    lines.extend(f"- {limitation}" for limitation in result.limitations)
    lines.extend(
        [
            "",
            "## Como reproducir",
            "",
            "```powershell",
            "python scripts\\run_backtest_correctness_audit.py",
            "python -m pytest tests\\test_backtest_correctness_audit.py",
            "```",
            "",
        ]
    )
    result.report_path.write_text("\n".join(lines), encoding="utf-8")


_CHECKS: tuple[Callable[[], CorrectnessCheck], ...] = (
    _check_flat_price_no_trades,
    _check_rising_buy_and_hold_exact_return,
    _check_one_trade_costs_and_slippage_exact_pnl,
    _check_signal_executes_next_bar,
    _check_missing_signal_handling,
    _check_duplicate_dates_rejected,
    _check_gap_stop_loss_rule,
    _check_insufficient_capital_is_sized_to_cash,
    _check_equity_accounting_and_drawdown,
    _check_benchmark_period_alignment,
)
