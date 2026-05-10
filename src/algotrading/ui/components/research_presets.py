from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.preset_adapter import ResearchPreset, preset_frame


def render_preset_summary(preset: ResearchPreset, *, expanded: bool = False) -> None:
    st.caption(preset.ui_text)
    with st.expander("Checklist del preset", expanded=expanded):
        st.dataframe(preset_frame(preset), width="stretch", hide_index=True)
        for check in preset.required_checks:
            st.markdown(f"- {check}")


def render_preset_badge(preset: ResearchPreset) -> None:
    st.info(f"Preset de research: **{preset.label}**. {preset.description}")
