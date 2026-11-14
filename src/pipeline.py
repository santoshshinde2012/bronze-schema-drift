"""Promote Bronze records to Silver through an adapter, hold the rest, and replay held records."""
from __future__ import annotations

import pandas as pd

from .models import Outcome
from .protocols import Adapter, SilverStore


def promote(records: pd.DataFrame, adapter: Adapter) -> Outcome:
    valid, held = [], []
    for record in records.to_dict("records"):
        record = {k: (None if isinstance(v, float) and v != v else v) for k, v in record.items()}
        row, reasons = adapter.apply(record)
        if row:
            valid.append(row)
        else:
            held.append({"order_id": record["order_id"], "_file": record["_file"], "_line": record["_line"],
                         "reasons": "; ".join(reasons), "adapter": adapter.version})
    return Outcome(valid, held)


def run_batch(store: SilverStore, records: pd.DataFrame, adapter: Adapter) -> Outcome:
    out = promote(records, adapter)
    store.upsert_valid(out.valid)
    store.replace_held(out.held)
    return out


def replay_held(store: SilverStore, bronze: pd.DataFrame, adapter: Adapter) -> Outcome:
    """Send held records back through the approved adapter, the same one the daily path uses."""
    held_ids = set(store.read_held()["order_id"])
    out = promote(bronze[bronze["order_id"].isin(held_ids)], adapter)
    store.upsert_valid(out.valid)
    store.replace_held(out.held)
    return out


def join_matches(silver: pd.DataFrame, customers: dict) -> int:
    return int(silver["customer_code"].isin(customers.keys()).sum())


def coverage(store: SilverStore, bronze: pd.DataFrame) -> dict:
    """Reconcile: every landed record is either valid or held."""
    valid, held = set(store.read_valid()["order_id"]), set(store.read_held()["order_id"])
    landed = set(bronze["order_id"])
    return {"landed": len(landed), "valid": len(valid), "held": len(held),
            "unaccounted": sorted(landed - valid - held)}
