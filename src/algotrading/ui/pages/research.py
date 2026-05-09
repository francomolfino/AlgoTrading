from __future__ import annotations

# Compatibility layer: page implementations now live in dedicated modules.
from algotrading.ui.pages._shared import *
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

__all__ = [name for name in globals() if name.startswith("render_")]
