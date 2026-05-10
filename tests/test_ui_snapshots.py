from algotrading.cli.capture_streamlit_snapshots import build_parser
from algotrading.ui.adapters.snapshot_adapter import (
    DEFAULT_SNAPSHOT_PAGES,
    build_snapshot_targets,
    slugify_page,
    snapshot_output_dir,
    snapshot_url,
)
from algotrading.ui.components.navigation import PAGES


def test_snapshot_targets_cover_all_pages_with_stable_filenames():
    targets = build_snapshot_targets("http://localhost:8502")

    assert [target.page for target in targets] == list(PAGES)
    assert len(targets) == len(DEFAULT_SNAPSHOT_PAGES)
    assert targets[0].filename == "01_home_overview.png"
    assert targets[0].url.endswith("?page=Home+%2F+Overview")
    assert all(target.filename.endswith(".png") for target in targets)


def test_snapshot_url_rejects_unknown_page():
    try:
        snapshot_url("http://localhost:8502", "Pagina falsa")
    except ValueError as exc:
        assert "Pagina no soportada" in str(exc)
    else:
        raise AssertionError("snapshot_url deberia rechazar paginas desconocidas")


def test_snapshot_slug_and_output_dir_are_predictable():
    assert slugify_page("Nuevo experimento guiado") == "nuevo_experimento_guiado"
    assert slugify_page("Reports / Export") == "reports_export"
    assert snapshot_output_dir().as_posix() == "reports/ui_snapshots"


def test_snapshot_cli_parser_accepts_subset_and_existing_server():
    args = build_parser().parse_args(
        [
            "--server-url",
            "http://localhost:8501",
            "--pages",
            "Home / Overview",
            "Results Dashboard",
            "--width",
            "1280",
            "--height",
            "900",
        ]
    )

    assert args.server_url == "http://localhost:8501"
    assert args.pages == ["Home / Overview", "Results Dashboard"]
    assert args.width == 1280
    assert args.height == 900
