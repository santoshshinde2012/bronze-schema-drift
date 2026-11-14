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


def _persist_outcome(store: SilverStore, out: Outcome, processed_ids: set) -> None:
    store.upsert_valid(out.valid)
    store.delete_valid([row["order_id"] for row in out.held])
    held = {
        row["order_id"]: row
        for row in store.read_held().to_dict("records")
        if row["order_id"] not in processed_ids
    }
    held.update({row["order_id"]: row for row in out.held})
    store.replace_held(list(held.values()))


def run_batch(store: SilverStore, records: pd.DataFrame, adapter: Adapter) -> Outcome:
    out = promote(records, adapter)
    _persist_outcome(store, out, set(records["order_id"]))
    return out


def replay_held(store: SilverStore, bronze: pd.DataFrame, adapter: Adapter) -> Outcome:
    """Send held records back through the approved adapter, the same one the daily path uses."""
    held_ids = set(store.read_held()["order_id"])
    records = bronze[bronze["order_id"].isin(held_ids)]
    out = promote(records, adapter)
    _persist_outcome(store, out, set(records["order_id"]))
    return out


def join_matches(silver: pd.DataFrame, customers: dict) -> int:
    return int(silver["customer_code"].isin(customers.keys()).sum())


def coverage(store: SilverStore, bronze: pd.DataFrame) -> dict:
    """Reconcile: every landed record is either valid or held."""
    valid, held = set(store.read_valid()["order_id"]), set(store.read_held()["order_id"])
    landed = set(bronze["order_id"])
    return {"landed": len(landed), "valid": len(valid), "held": len(held),
            "unaccounted": sorted(landed - valid - held)}
