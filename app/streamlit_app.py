from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MPLCONFIGDIR = ROOT / ".cache" / "matplotlib"
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import streamlit as st

from algotrading.ui.components.navigation import PAGES, init_state, render_sidebar
from algotrading.ui.pages import PAGE_RENDERERS, render_placeholder


def main() -> None:
    st.set_page_config(page_title="AlgoTrading Lab", layout="wide")
    init_state()
    render_sidebar()

    page = st.session_state.get("page", PAGES[0])
    renderer = PAGE_RENDERERS.get(page)
    if renderer is None:
        render_placeholder(page)
        return
    renderer()


if __name__ == "__main__":
    main()
