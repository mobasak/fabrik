"""Scenario 05: Breaking change."""


def process_payment(amount: float, currency: str = "USD") -> dict:
    # BREAKING: Changed return type from bool to dict
    return {"status": "ok", "amount": amount, "currency": currency}
