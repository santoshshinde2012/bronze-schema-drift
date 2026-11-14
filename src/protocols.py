"""Interfaces the pipeline depends on."""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class Adapter(Protocol):
    """Maps one approved source shape into Silver's model. Returns a Silver row, or the reasons to hold it."""

    version: str

    def apply(self, record: dict) -> tuple[dict | None, list[str]]: ...


class SilverStore(Protocol):
    """Silver orders and the held records, as tables."""

    def upsert_valid(self, rows: list[dict]) -> None: ...

    def replace_held(self, rows: list[dict]) -> None: ...

    def read_valid(self) -> pd.DataFrame: ...

    def read_held(self) -> pd.DataFrame: ...
