from __future__ import annotations

import argparse
from contextlib import suppress
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from algotrading.ui.adapters.snapshot_adapter import (
    DEFAULT_SNAPSHOT_PAGES,
    build_snapshot_targets,
    snapshot_output_dir,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Captura snapshots visuales de la app Streamlit local."
    )
    parser.add_argument(
        "--pages",
        nargs="*",
        default=list(DEFAULT_SNAPSHOT_PAGES),
        help="Paginas a capturar. Por defecto captura todas las paginas principales.",
    )
    parser.add_argument("--output-dir", default="reports/ui_snapshots", help="Carpeta de salida PNG.")
    parser.add_argument("--host", default="127.0.0.1", help="Host local de Streamlit.")
    parser.add_argument("--port", type=int, default=8502, help="Puerto local para levantar Streamlit.")
    parser.add_argument(
        "--server-url",
        default=None,
        help="Usa una app Streamlit ya levantada, por ejemplo http://localhost:8501.",
    )
    parser.add_argument("--width", type=int, default=1440, help="Ancho del viewport.")
    parser.add_argument("--height", type=int, default=1100, help="Alto del viewport.")
    parser.add_argument("--timeout", type=int, default=45, help="Timeout de arranque en segundos.")
    parser.add_argument(
        "--keep-server",
        action="store_true",
        help="No cierra el proceso de Streamlit al terminar, si este script lo levanto.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = snapshot_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_url = args.server_url or f"http://{args.host}:{args.port}"
    streamlit_process = None
    log_handle = None

    try:
        if args.server_url is None:
            log_path = output_dir / "streamlit_snapshot_server.log"
            log_handle = log_path.open("w", encoding="utf-8")
            streamlit_process = _start_streamlit(args.host, args.port, log_handle)
        _wait_for_server(base_url, timeout_seconds=args.timeout)
        _capture_pages(
            base_url=base_url,
            output_dir=output_dir,
            pages=args.pages,
            viewport={"width": args.width, "height": args.height},
        )
        print(f"[ok] snapshots -> {output_dir.resolve()}")
        return 0
    finally:
        if streamlit_process is not None and not args.keep_server:
            _stop_process(streamlit_process)
        if log_handle is not None:
            log_handle.close()


def _start_streamlit(host: str, port: int, log_handle) -> subprocess.Popen:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app/streamlit_app.py",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--server.address",
        host,
        "--server.port",
        str(port),
    ]
    return subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)


def _wait_for_server(base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with suppress(URLError, TimeoutError, ConnectionError):
            with urlopen(base_url, timeout=2) as response:
                if response.status < 500:
                    return
        time.sleep(0.5)
    raise RuntimeError(f"Streamlit no respondio en {base_url} despues de {timeout_seconds}s.")


def _capture_pages(
    *,
    base_url: str,
    output_dir: Path,
    pages: list[str],
    viewport: dict[str, int],
) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Falta Playwright. Instala con: python -m pip install -e .[ui,visual] "
            "y luego: python -m playwright install chromium"
        ) from exc

    targets = build_snapshot_targets(base_url, pages)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=viewport)
        for target in targets:
            page.goto(target.url, wait_until="domcontentloaded")
            with suppress(PlaywrightTimeoutError):
                page.wait_for_load_state("networkidle", timeout=5_000)
            page.wait_for_timeout(1_000)
            output_path = output_dir / target.filename
            page.screenshot(path=str(output_path), full_page=True)
            print(f"[ok] {target.page} -> {output_path}")
        browser.close()


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
