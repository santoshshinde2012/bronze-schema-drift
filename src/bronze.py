"""Land files in Bronze like a reader in rescue mode: keep approved fields, put everything else in `_rescued_data`."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import BRONZE_COLUMNS, Drift


def read_file(path: Path, approved: list[str]) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        record = json.loads(line)
        row = {f: record.get(f) for f in approved}
        extra = {k: v for k, v in record.items() if k not in approved}
        row["_rescued_data"] = json.dumps({**extra, "_file_path": path.name}) if extra else None
        row["_file"], row["_line"] = path.name, line_no
        rows.append(row)
    return rows


def drift(path: Path, approved: list[str]) -> Drift:
    """Compare every record's fields with the approved schema, not only the file's combined shape."""
    records = [json.loads(line) for line in path.read_text().splitlines()]
    seen = set().union(*(r.keys() for r in records))
    shapes = {tuple(sorted(r.keys())) for r in records}
    missing = {f for f in approved if any(f not in r for r in records)}
    return Drift(path.name, tuple(sorted(seen - set(approved))), tuple(sorted(missing)), len(shapes))


def to_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=BRONZE_COLUMNS)
