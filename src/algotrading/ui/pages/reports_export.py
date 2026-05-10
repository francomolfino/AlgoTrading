from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.reports_adapter import build_experiment_zip, collect_experiment_report_files
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.selectors import experiment_selector as _experiment_selector


def render_reports_export() -> None:
    st.title("Reports / Export")
    record = _experiment_selector("reports_experiment")
    if record is None:
        st.info("No hay experimentos guardados.")
        return
    files = collect_experiment_report_files(record.path)
    st.write(f"Carpeta: `{record.path}`")
    try:
        st.download_button(
            "Descargar experimento completo ZIP",
            data=build_experiment_zip(record.path),
            file_name=f"{record.path.name}.zip",
            mime="application/zip",
        )
    except Exception as exc:
        _show_error(exc)
    if not files:
        st.warning("No encontre archivos exportables.")
        return
    for report_file in files:
        col1, col2 = st.columns([3, 1])
        col1.write(f"`{report_file.label}`")
        col2.download_button(
            "Descargar",
            data=report_file.path.read_bytes(),
            file_name=report_file.path.name,
            mime=report_file.mime,
            key=f"download_{report_file.path}",
        )
