from __future__ import annotations

from algotrading.ui.components.navigation import PAGES
from algotrading.ui.components.common import render_placeholder
from algotrading.ui.pages.backtest_runner import render_backtest_runner
from algotrading.ui.pages.data_manager import render_data_manager
from algotrading.ui.pages.experiment_explorer import render_experiment_explorer
from algotrading.ui.pages.guided_workflow import render_guided_workflow
from algotrading.ui.pages.home import render_home
from algotrading.ui.pages.paper_trading import render_paper_trading_simulator
from algotrading.ui.pages.portfolio_lab import render_portfolio_lab
from algotrading.ui.pages.reports_export import render_reports_export
from algotrading.ui.pages.results_dashboard import render_results_dashboard
from algotrading.ui.pages.risk_manager import render_risk_manager_lab
from algotrading.ui.pages.robustness_lab import render_robustness_lab
from algotrading.ui.pages.settings import render_settings
from algotrading.ui.pages.stress_tests import render_stress_tests
from algotrading.ui.pages.strategy_lab import render_strategy_lab


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
