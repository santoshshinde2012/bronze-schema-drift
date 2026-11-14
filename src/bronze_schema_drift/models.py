"""Columns and small value objects."""
from __future__ import annotations

from dataclasses import dataclass

BRONZE_COLUMNS = ["order_id", "customer_code", "amount", "_rescued_data", "_file", "_line"]
SILVER_COLUMNS = ["order_id", "customer_code", "amount", "adapter"]
HELD_COLUMNS = ["order_id", "_file", "_line", "reasons", "adapter"]
KEY_FIELDS = {"customer_code", "account_code"}


@dataclass(frozen=True)
class Drift:
    """How one landed file differs from the approved schema, and how many record shapes it holds."""

    file: str
    added: tuple
    missing: tuple
    shapes: int


@dataclass(frozen=True)
class Outcome:
    """What one Silver run did with a batch of Bronze records."""

    valid: list
    held: list
