from __future__ import annotations

from algotrading.ui.components.navigation import PAGES
from algotrading.ui.pages.research import (
    render_backtest_runner,
    render_data_manager,
    render_experiment_explorer,
    render_guided_workflow,
    render_home,
    render_paper_trading_simulator,
    render_placeholder,
    render_portfolio_lab,
    render_reports_export,
    render_results_dashboard,
    render_risk_manager_lab,
    render_robustness_lab,
    render_settings,
    render_stress_tests,
    render_strategy_lab,
)


PAGE_RENDERERS = {
    "Home / Overview": render_home,
    "Nuevo experimento guiado": render_guided_workflow,
    "Data Manager": render_data_manager,
    "Strategy Lab": render_strategy_lab,
    "Backtest Runner": render_backtest_runner,
    "Results Dashboard": render_results_dashboard,
    "Experiment Explorer": render_experiment_explorer,
    "Robustness Lab": render_robustness_lab,
    "Stress Tests": render_stress_tests,
    "Portfolio Lab": render_portfolio_lab,
    "Risk Manager": render_risk_manager_lab,
    "Paper Trading Simulator": render_paper_trading_simulator,
    "Reports / Export": render_reports_export,
    "Settings": render_settings,
}

assert set(PAGE_RENDERERS) == set(PAGES)
