from __future__ import annotations

from algotrading.ui.pages._shared import *


def render_strategy_lab() -> None:
    st.title("Strategy Lab")
    st.info("Esta pantalla muestra intenciones de senal, no rentabilidad. El backtester aplica delay para evitar lookahead.")
    asset = _asset_selector("strategy_asset")
    if asset is None:
        st.info("Primero carga datos en Data Manager.")
        return

    strategy_key = _strategy_selector("strategy_lab_strategy")
    config = get_strategy_config(strategy_key)
    st.write(config.description)
    st.caption(config.risk_note)
    _render_strategy_research_metadata(strategy_key)
    parameters = _render_strategy_parameters(strategy_key, "strategy_lab")

    try:
        frame = load_data_file(asset.path)
        warnings = validate_strategy_parameters(strategy_key, parameters, frame_length=len(frame))
        for warning in warnings:
            st.warning(warning)
        signal_frame = generate_strategy_signals(frame, strategy_key, parameters)
        summary = signal_summary(signal_frame)
    except Exception as exc:
        _show_error(exc)
        return

    cols = st.columns(4)
    cols[0].metric("Entradas", summary["entries"])
    cols[1].metric("Salidas", summary["exits"])
    cols[2].metric("Barras long", summary["bars_in_market"])
    cols[3].metric("Exposicion senal", f"{summary['exposure_ratio']:.1%}")
    _render_signal_reading(strategy_key, summary, len(signal_frame))
    render_price_volume_chart(
        signal_frame,
        title=f"{asset.symbol_hint} - senales {STRATEGIES[strategy_key].label}",
        price_column="adj_close" if "adj_close" in signal_frame else "close",
        overlay_columns=_price_overlay_columns(signal_frame),
        signal_column="signal",
        height=560,
    )
    _render_signal_tables(signal_frame)
