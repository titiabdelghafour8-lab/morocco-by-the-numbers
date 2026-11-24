"""ODbL data files: the processed figures behind each page, as JSON (and CSV for tables)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def to_json(data: dict[str, Any]) -> str:
    """Published, human-readable form (one space indent, UTF-8 kept)."""
    return json.dumps(data, ensure_ascii=False, indent=1)


def to_min_json(data: dict[str, Any]) -> str:
    """Compact form, embedded in pages."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, to_json(data))


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    write_text(path, to_csv(rows, columns))
