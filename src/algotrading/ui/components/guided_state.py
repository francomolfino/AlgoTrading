from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.guided_adapter import ExperimentDraft, new_experiment_draft


def get_guided_draft() -> ExperimentDraft:
    draft = st.session_state.get("experiment_draft")
    if not isinstance(draft, ExperimentDraft):
        draft = new_experiment_draft(st.session_state.get("interval", "1d"))
        st.session_state.experiment_draft = draft
    return draft


def set_guided_draft(draft: ExperimentDraft) -> None:
    st.session_state.experiment_draft = draft
    st.session_state.pending_guided_step = draft.step
