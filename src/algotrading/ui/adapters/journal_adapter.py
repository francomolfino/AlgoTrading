from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


RESEARCH_NOTE_STATUSES = (
    "Draft",
    "Needs Review",
    "Rejected",
    "Promising",
    "Robustness Passed",
    "Paper Simulation Candidate",
    "Archived",
)
DEFAULT_RESEARCH_STATUS = "Draft"
RESEARCH_NOTES_FILENAME = "research_notes.json"


@dataclass(frozen=True)
class ResearchNotes:
    status: str = DEFAULT_RESEARCH_STATUS
    hypothesis: str = ""
    conclusion: str = ""
    next_test: str = ""
    tags: tuple[str, ...] = ()
    favorite: bool = False
    updated_at_utc: str = ""


def load_research_notes(experiment_dir: Path | str) -> ResearchNotes:
    path = _notes_path(experiment_dir)
    if not path.exists():
        return ResearchNotes()

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        return ResearchNotes()
    return _notes_from_payload(payload)


def save_research_notes(experiment_dir: Path | str, notes: ResearchNotes) -> Path:
    directory = Path(experiment_dir)
    directory.mkdir(parents=True, exist_ok=True)
    normalized = ResearchNotes(
        status=_normalize_status(notes.status),
        hypothesis=notes.hypothesis.strip(),
        conclusion=notes.conclusion.strip(),
        next_test=notes.next_test.strip(),
        tags=parse_tags(notes.tags),
        favorite=bool(notes.favorite),
        updated_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    path = _notes_path(directory)
    with path.open("w", encoding="utf-8") as file:
        json.dump(_notes_payload(normalized), file, indent=2, sort_keys=True)
        file.write("\n")
    return path


def parse_tags(value: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_tags = value.replace(";", ",").split(",")
    else:
        raw_tags = [str(item) for item in value]

    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        tag = item.strip().lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tuple(tags)


def tags_to_text(tags: tuple[str, ...] | list[str]) -> str:
    return ", ".join(parse_tags(tuple(tags)))


def _notes_path(experiment_dir: Path | str) -> Path:
    return Path(experiment_dir) / RESEARCH_NOTES_FILENAME


def _notes_from_payload(payload: dict[str, Any]) -> ResearchNotes:
    return ResearchNotes(
        status=_normalize_status(str(payload.get("status", DEFAULT_RESEARCH_STATUS))),
        hypothesis=str(payload.get("hypothesis", "")),
        conclusion=str(payload.get("conclusion", "")),
        next_test=str(payload.get("next_test", "")),
        tags=parse_tags(payload.get("tags", [])),
        favorite=bool(payload.get("favorite", False)),
        updated_at_utc=str(payload.get("updated_at_utc", "")),
    )


def _notes_payload(notes: ResearchNotes) -> dict[str, Any]:
    return {
        "status": notes.status,
        "hypothesis": notes.hypothesis,
        "conclusion": notes.conclusion,
        "next_test": notes.next_test,
        "tags": list(notes.tags),
        "favorite": notes.favorite,
        "updated_at_utc": notes.updated_at_utc,
    }


def _normalize_status(status: str) -> str:
    return status if status in RESEARCH_NOTE_STATUSES else DEFAULT_RESEARCH_STATUS
