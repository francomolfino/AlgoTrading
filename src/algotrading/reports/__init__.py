"""Reportes automaticos para research."""

from algotrading.reports.backtest import (
    BacktestReportArtifacts,
    build_exposure_summary,
    build_metrics_table,
    build_period_extremes,
    build_report_comment,
    calculate_monthly_returns,
    generate_backtest_report,
)

__all__ = [
    "BacktestReportArtifacts",
    "build_exposure_summary",
    "build_metrics_table",
    "build_period_extremes",
    "build_report_comment",
    "calculate_monthly_returns",
    "generate_backtest_report",
]
