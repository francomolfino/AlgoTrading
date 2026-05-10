from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode, urljoin

from algotrading.ui.components.navigation import PAGES


DEFAULT_SNAPSHOT_PAGES = tuple(PAGES)


@dataclass(frozen=True)
class SnapshotTarget:
    page: str
    filename: str
    url: str


def build_snapshot_targets(
    base_url: str,
    pages: list[str] | tuple[str, ...] | None = None,
) -> list[SnapshotTarget]:
    selected_pages = tuple(pages or DEFAULT_SNAPSHOT_PAGES)
    unsupported = [page for page in selected_pages if page not in PAGES]
    if unsupported:
        raise ValueError(f"Paginas no soportadas para snapshots: {', '.join(unsupported)}")
    return [
        SnapshotTarget(
            page=page,
            filename=f"{index:02d}_{slugify_page(page)}.png",
            url=snapshot_url(base_url, page),
        )
        for index, page in enumerate(selected_pages, start=1)
    ]


def snapshot_url(base_url: str, page: str) -> str:
    if page not in PAGES:
        raise ValueError(f"Pagina no soportada: {page}")
    normalized_base = base_url if base_url.endswith("/") else f"{base_url}/"
    return urljoin(normalized_base, f"?{urlencode({'page': page})}")


def snapshot_output_dir(path: str | Path | None = None) -> Path:
    return Path(path or "reports/ui_snapshots")


def slugify_page(page: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", page).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug or "page"
