from __future__ import annotations

# Compatibility layer: shared UI implementations live in components.
from algotrading.ui.components.common import (
    render_bullets as _render_bullets,
    render_placeholder,
    show_error as _show_error,
)
from algotrading.ui.components.data_quality import render_data_quality_reading as _render_data_quality_reading
from algotrading.ui.components.equity_comparison import (
    combined_equity_frame as _combined_equity_frame,
    comparison_has_mismatch as _comparison_has_mismatch,
)
from algotrading.ui.components.experiment_config import (
    experiment_request_defaults as _experiment_request_defaults,
    render_experiment_config_summary as _render_experiment_config_summary,
)
from algotrading.ui.components.guided_state import (
    get_guided_draft as _get_guided_draft,
    set_guided_draft as _set_guided_draft,
)
from algotrading.ui.components.home_overview import render_next_step as _render_next_step
from algotrading.ui.components.journal_actions import (
    render_linked_journal_status_action as _render_linked_journal_status_action,
)
from algotrading.ui.components.preflight import (
    render_backtest_preflight as _render_backtest_preflight,
    render_portfolio_preflight as _render_portfolio_preflight,
)
from algotrading.ui.components.research_results import (
    matching_robustness as _matching_robustness,
    matching_stress_test as _matching_stress_test,
    render_backtest_result as _render_backtest_result,
    render_experiment_details as _render_experiment_details,
)
from algotrading.ui.components.risk_controls import render_risk_settings as _render_risk_settings
from algotrading.ui.components.selectors import (
    asset_index as _asset_index,
    asset_selector as _asset_selector,
    experiment_selector as _experiment_selector,
    strategy_index as _strategy_index,
    strategy_selector as _strategy_selector,
)
from algotrading.ui.components.signal_insights import (
    price_overlay_columns as _price_overlay_columns,
    render_signal_reading as _render_signal_reading,
)
from algotrading.ui.components.strategy_controls import (
    render_strategy_parameters as _render_strategy_parameters,
    render_strategy_research_metadata as _render_strategy_research_metadata,
)

__all__ = [name for name in globals() if not name.startswith("__")]
