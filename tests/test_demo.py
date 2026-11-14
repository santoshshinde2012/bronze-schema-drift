"""Lock the claims the article makes about the local run."""
from __future__ import annotations

import pytest

from src.adapters import ContractV1, try_decimal
from src.demo import run


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    return run(tmp_path_factory.mktemp("lake"))


def test_bronze_lands_everything_and_rescues_the_new_field(result):
    assert result["bronze"] == {"records": 8, "with_rescued_data": 4}
    assert result["rescued_example"] == '{"account_code": "A-72", "_file_path": "orders_0602.json"}'


def test_old_silver_step_succeeds_with_silent_nulls(result):
    assert result["naive"] == {"rows": 8, "customer_code_null": 3, "amount_null": 1, "join_matches": 5}


def test_drift_is_found_per_record(result):
    assert result["drift"] == [("orders_0601.json", [], [], 1),
                               ("orders_0602.json", ["account_code"], ["customer_code"], 1),
                               ("orders_0603.json", ["account_code"], [], 2)]


def test_contract_holds_with_reasons_and_accounts_for_every_record(result):
    c = result["contract_v1"]
    assert c["valid"] == ["o1", "o2", "o3", "o7"]
    assert [h[0] for h in c["held"]] == ["o4", "o5", "o6", "o8"]
    assert "amount did not parse" in c["held"][1][1]
    assert c["coverage"] == {"landed": 8, "valid": 4, "held": 4, "unaccounted": []}


def test_fallback_hides_a_conflict(result):
    assert result["fallback_o8"] == {"fallback_says": "C-1", "account_A72_means": "C-4"}


def test_replay_through_the_approved_adapter(result):
    r = result["replay_1"]
    assert r["released"] == ["o4", "o5", "o6"]
    assert r["still_held"] == [("o8", "customer_code C-1 and account A-72 (C-4) disagree")]
    assert (r["silver_rows"], r["join_matches"]) == (7, 7)


def test_second_replay_adds_no_duplicates_and_matches_a_fresh_run(result):
    assert result["replay_2_silver_rows"] == 7
    assert result["matches_fresh_run"] is True


def test_missing_and_unparseable_amounts_get_different_reasons():
    base = {"order_id": "x", "customer_code": "C-1", "_rescued_data": None}
    assert ContractV1().apply({**base, "amount": None})[1] == ["amount missing"]
    assert ContractV1().apply({**base, "amount": "1,5"})[1] == ["amount did not parse"]
    assert str(try_decimal("12,50", decimal_comma=True)) == "12.50"
