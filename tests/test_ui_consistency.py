from algotrading.ui.components.navigation import AREA_DESCRIPTIONS, PAGES, PAGE_AREAS, page_area
from algotrading.ui.texts import EMPTY_STATES, RESEARCH_FLOW_STEPS, TOOLTIPS


def test_navigation_pages_have_conceptual_areas():
    assert set(PAGE_AREAS) == set(PAGES)
    assert all(page_area(page) in AREA_DESCRIPTIONS for page in PAGES)
    assert page_area("Paper Trading Simulator") == "Paper Runtime"
    assert page_area("Settings") == "Sistema"


def test_empty_states_are_actionable_and_consistent():
    required = {"title", "missing", "why", "next"}

    assert {"no_data", "no_experiments", "no_latest_backtest", "no_paper_session"}.issubset(EMPTY_STATES)
    for payload in EMPTY_STATES.values():
        assert required.issubset(payload)
        assert all(str(payload[key]).strip() for key in required)


def test_research_flow_and_tooltips_cover_core_terms():
    assert RESEARCH_FLOW_STEPS[0].startswith("1.")
    assert "paper trading simulado" in RESEARCH_FLOW_STEPS[-1].lower()
    for key in [
        "slippage",
        "commission",
        "benchmark",
        "evidence_score",
        "research_verdict",
        "data_quality_score",
        "walk_forward",
        "stress_test",
        "drawdown",
        "sharpe",
        "exposure",
        "paper_trading",
        "live_market_data",
        "simulated_broker",
    ]:
        assert TOOLTIPS[key]
