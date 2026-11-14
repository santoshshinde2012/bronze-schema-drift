"""Run the article's example on local Delta tables and print what happened."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import deltalake

from .adapters import ContractV1, ContractV2, FallbackGuess, PassThrough
from .bronze import drift, read_file
from .pipeline import coverage, join_matches, promote, replay_held, run_batch
from .repository import BronzeTable, SilverTables

HERE = Path(__file__).resolve().parent.parent


def _held(store) -> list:
    return [(r["order_id"], r["reasons"]) for r in store.read_held().to_dict("records")]


def run(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)
    ref = json.loads((HERE / "data" / "reference.json").read_text())
    approved, customers, accounts = ref["approved_schema_v1"], ref["customers"], ref["accounts_confirmed_by_source_owner"]
    files = sorted((HERE / "data" / "landing").glob("*.json"))
    out: dict = {"deltalake": deltalake.__version__}

    # 1. Bronze lands every file in rescue mode. Nothing fails.
    bronze = BronzeTable(root)
    for f in files:
        bronze.append(read_file(f, approved))
    landed = bronze.read()
    out["bronze"] = {"records": len(landed), "with_rescued_data": int(landed["_rescued_data"].notna().sum())}
    out["rescued_example"] = landed.loc[landed["order_id"] == "o4", "_rescued_data"].iloc[0]

    # 2. The old Silver step: select the approved columns and cast. It also succeeds.
    naive = SilverTables(root, "naive")
    run_batch(naive, landed, PassThrough())
    s = naive.read_valid()
    out["naive"] = {"rows": len(s), "customer_code_null": int(s["customer_code"].isna().sum()),
                    "amount_null": int(s["amount"].isna().sum()), "join_matches": join_matches(s, customers)}

    # 3. Compare each file, record by record, with the approved schema.
    out["drift"] = [(d.file, list(d.added), list(d.missing), d.shapes) for d in (drift(f, approved) for f in files)]

    # 4. A Silver contract holds what it cannot vouch for.
    silver = SilverTables(root, "silver")
    run_batch(silver, landed, ContractV1())
    out["contract_v1"] = {"valid": sorted(silver.read_valid()["order_id"]), "held": _held(silver),
                          "coverage": coverage(silver, landed)}

    # 5. The tempting fallback, applied to everything.
    guess = {r["order_id"]: r["customer_code"] for r in promote(landed, FallbackGuess(accounts)).valid}
    out["fallback_o8"] = {"fallback_says": guess["o8"], "account_A72_means": accounts["A-72"]}

    # 6. The source owner confirms the mapping and the decimal comma. Replay held records through v2.
    released = replay_held(silver, landed, ContractV2(accounts))
    out["replay_1"] = {"released": sorted(r["order_id"] for r in released.valid), "still_held": _held(silver),
                       "silver_rows": len(silver.read_valid()), "join_matches": join_matches(silver.read_valid(), customers)}
    replay_held(silver, landed, ContractV2(accounts))
    out["replay_2_silver_rows"] = len(silver.read_valid())

    # 7. Compare with a fresh run of the same Bronze version through v2 only.
    fresh = SilverTables(root, "fresh")
    run_batch(fresh, landed, ContractV2(accounts))
    a = silver.read_valid()[["order_id", "customer_code", "amount"]]
    b = fresh.read_valid()[["order_id", "customer_code", "amount"]]
    out["matches_fresh_run"] = a.equals(b) and _held(silver) == _held(fresh)
    out["silver_after"] = [(r["order_id"], r["customer_code"], str(r["amount"]), r["adapter"]) for r in silver.read_valid().to_dict("records")]
    return out


def main() -> None:
    out = run(HERE / "lake")
    print(f"deltalake {out['deltalake']} on local disk; not a Databricks runtime; reader mimics rescue mode")
    print(f"1. Bronze: {out['bronze']}. Rescued for o4: {out['rescued_example']}")
    print(f"2. Old Silver step succeeded: {out['naive']}")
    print(f"3. Drift by file (file, added, missing, record shapes): {out['drift']}")
    c = out["contract_v1"]
    print(f"4. Contract v1: valid {c['valid']}; coverage {c['coverage']}")
    for h in c["held"]:
        print(f"   held {h}")
    print(f"5. Fallback guess for o8: {out['fallback_o8']}")
    r = out["replay_1"]
    print(f"6. Replay through v2: released {r['released']}; still held {r['still_held']}; Silver rows {r['silver_rows']}, join matches {r['join_matches']}")
    print(f"   Second identical replay: Silver rows {out['replay_2_silver_rows']}")
    print(f"7. Matches a fresh run of the same Bronze through v2: {out['matches_fresh_run']}")


if __name__ == "__main__":
    main()
