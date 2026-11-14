"""How a Bronze record becomes a Silver row. Each approved version is one class."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from .models import KEY_FIELDS


def try_decimal(text: str | None, decimal_comma: bool = False) -> Decimal | None:
    """Like TRY_CAST: None when the text does not parse."""
    if text is None:
        return None
    if decimal_comma:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def rescued(record: dict) -> dict:
    return json.loads(record["_rescued_data"]) if record.get("_rescued_data") else {}


class PassThrough:
    """The pipeline before the change: select the approved columns and cast. No checks."""

    version = "none"

    def apply(self, record: dict) -> tuple[dict | None, list[str]]:
        return {"order_id": record["order_id"], "customer_code": record["customer_code"],
                "amount": try_decimal(record["amount"]), "adapter": self.version}, []


class ContractV1:
    """The Silver contract for the approved shape. Anything it cannot vouch for is held with reasons."""

    version = "v1"

    def apply(self, record: dict) -> tuple[dict | None, list[str]]:
        reasons = []
        unknown_keys = sorted(KEY_FIELDS & rescued(record).keys())
        if unknown_keys:
            reasons.append("unapproved key field in rescued data: " + ", ".join(unknown_keys))
        if not record["customer_code"]:
            reasons.append("customer_code missing")
        amount = try_decimal(record["amount"])
        if record["amount"] is None:
            reasons.append("amount missing")
        elif amount is None:
            reasons.append("amount did not parse")
        if reasons:
            return None, reasons
        return {"order_id": record["order_id"], "customer_code": record["customer_code"],
                "amount": amount, "adapter": self.version}, []


class FallbackGuess:
    """The tempting fix: take customer_code, else map account_code. No conflict check."""

    version = "fallback"

    def __init__(self, accounts: dict) -> None:
        self.accounts = accounts

    def apply(self, record: dict) -> tuple[dict | None, list[str]]:
        account = rescued(record).get("account_code")
        customer = record["customer_code"] or self.accounts.get(account)
        return {"order_id": record["order_id"], "customer_code": customer,
                "amount": try_decimal(record["amount"], decimal_comma=True), "adapter": self.version}, []


class ContractV2:
    """Approved after the source owner confirmed the account mapping and the decimal comma."""

    version = "v2"

    def __init__(self, accounts: dict) -> None:
        self.accounts = accounts

    def apply(self, record: dict) -> tuple[dict | None, list[str]]:
        extra = rescued(record)
        account = extra.get("account_code")
        mapped = self.accounts.get(account) if account else None
        customer = record["customer_code"]
        reasons = []
        if account and not mapped:
            reasons.append(f"account {account} not in the confirmed mapping")
        if customer and mapped and customer != mapped:
            reasons.append(f"customer_code {customer} and account {account} ({mapped}) disagree")
        customer = customer or mapped
        if not customer:
            reasons.append("customer_code missing")
        amount = try_decimal(record["amount"], decimal_comma=bool(account))
        if amount is None:
            reasons.append("amount missing or did not parse")
        if reasons:
            return None, reasons
        return {"order_id": record["order_id"], "customer_code": customer, "amount": amount, "adapter": self.version}, []
