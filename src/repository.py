"""Bronze, Silver and held records as local Delta tables (open-source `deltalake`)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from .models import HELD_COLUMNS, SILVER_COLUMNS

BRONZE = pa.schema([("order_id", pa.string()), ("customer_code", pa.string()), ("amount", pa.string()),
                    ("_rescued_data", pa.string()), ("_file", pa.string()), ("_line", pa.int64())])
SILVER = pa.schema([("order_id", pa.string()), ("customer_code", pa.string()),
                    ("amount", pa.decimal128(18, 2)), ("adapter", pa.string())])
HELD = pa.schema([("order_id", pa.string()), ("_file", pa.string()), ("_line", pa.int64()),
                  ("reasons", pa.string()), ("adapter", pa.string())])


class BronzeTable:
    def __init__(self, root: Path) -> None:
        self.path = str(root / "bronze_orders")

    def append(self, rows: list[dict]) -> int:
        mode = "append" if Path(self.path).exists() else "overwrite"
        write_deltalake(self.path, pa.Table.from_pylist(rows, schema=BRONZE), mode=mode)
        return DeltaTable(self.path).version()

    def read(self, version: int | None = None) -> pd.DataFrame:
        return DeltaTable(self.path, version=version).to_pandas().sort_values(["_file", "_line"]).reset_index(drop=True)


class SilverTables:
    """Valid orders keyed by order_id, and held records keyed by order_id."""

    def __init__(self, root: Path, name: str = "silver") -> None:
        self.valid_path = str(root / f"{name}_orders")
        self.held_path = str(root / f"{name}_held")

    def upsert_valid(self, rows: list[dict]) -> None:
        if not rows:
            return
        data = pa.Table.from_pylist(rows, schema=SILVER)
        if not Path(self.valid_path).exists():
            write_deltalake(self.valid_path, data)
            return
        (DeltaTable(self.valid_path).merge(data, "t.order_id = s.order_id", source_alias="s", target_alias="t")
         .when_matched_update_all().when_not_matched_insert_all().execute())

    def replace_held(self, rows: list[dict]) -> None:
        write_deltalake(self.held_path, pa.Table.from_pylist(rows, schema=HELD), mode="overwrite")

    def read_valid(self) -> pd.DataFrame:
        if not Path(self.valid_path).exists():
            return pd.DataFrame(columns=SILVER_COLUMNS)
        return DeltaTable(self.valid_path).to_pandas().sort_values("order_id").reset_index(drop=True)

    def read_held(self) -> pd.DataFrame:
        if not Path(self.held_path).exists():
            return pd.DataFrame(columns=HELD_COLUMNS)
        return DeltaTable(self.held_path).to_pandas().sort_values("order_id").reset_index(drop=True)
