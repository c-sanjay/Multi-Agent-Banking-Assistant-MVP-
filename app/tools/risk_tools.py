"""Tools owned by the Risk / Fraud agent.

Scoring is deterministic and rule-based on purpose: the LLM explains the result but does
not invent it. That keeps fraud decisions auditable and reproducible.
"""
from datetime import datetime
from statistics import mean

from app.db import query, query_one
from app.tools.registry import tool

FLAG_THRESHOLD = 50  # score >= 50 -> flagged


def _score(txn: dict, history: list[dict], customer: dict, trusted_devices: set[str]) -> dict:
    """Return {score, level, reasons} for one transaction."""
    score, reasons = 0, []
    amounts = [h["amount"] for h in history if h["id"] != txn["id"]]
    avg = mean(amounts) if amounts else 0

    if avg and txn["amount"] > 5 * avg:
        score += 35
        reasons.append(f"Amount ₹{txn['amount']:,.0f} is {txn['amount'] / avg:.1f}x the customer's average (₹{avg:,.0f})")
    elif avg and txn["amount"] > 3 * avg:
        score += 15
        reasons.append(f"Amount is {txn['amount'] / avg:.1f}x the customer's average")

    if txn["country"] != customer["home_country"]:
        score += 30
        reasons.append(f"Foreign transaction (country: {txn['country']}, home: {customer['home_country']})")

    hour = datetime.fromisoformat(txn["ts"]).hour
    if hour < 5:
        score += 15
        reasons.append(f"Unusual hour ({hour:02d}:00, between 00:00 and 05:00)")

    if txn["device_id"] not in trusted_devices:
        score += 20
        reasons.append(f"Unrecognised device ({txn['device_id']})")

    # Card-testing velocity: several small charges at the same merchant within an hour
    same = [h for h in history if h["merchant"] == txn["merchant"] and h["id"] != txn["id"]
            and abs((datetime.fromisoformat(h["ts"]) - datetime.fromisoformat(txn["ts"])).total_seconds()) < 3600]
    if len(same) >= 2:
        score += 20
        reasons.append(f"{len(same) + 1} charges at {txn['merchant']} within one hour (possible card testing)")

    score = min(score, 100)
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= FLAG_THRESHOLD else "LOW"
    return {"score": score, "level": level, "reasons": reasons}


def _context(customer_id: str):
    customer = query_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    history = query("SELECT * FROM transactions WHERE customer_id = ? ORDER BY ts DESC", (customer_id,))
    trusted = {d["device_id"] for d in query(
        "SELECT device_id FROM devices WHERE customer_id = ? AND trusted = 1", (customer_id,))}
    return customer, history, trusted


@tool(
    agent="risk",
    description=("Score ONE transaction for fraud risk (0-100) with reasons. Identify it by "
                 "transaction_id, or by amount if the customer only knows the amount."),
    properties={
        "transaction_id": {"type": "string", "description": "e.g. TXN-9001"},
        "amount": {"type": "number", "description": "Transaction amount in INR, used if no id is known."},
    },
)
def score_transaction_risk(customer_id: str, transaction_id: str | None = None,
                           amount: float | None = None) -> dict:
    customer, history, trusted = _context(customer_id)
    txn = None
    if transaction_id:
        txn = next((h for h in history if h["id"] == transaction_id), None)
    elif amount is not None:
        txn = next((h for h in history if abs(h["amount"] - float(amount)) < 1), None)
    if not txn:
        return {"error": "transaction not found for this customer"}
    result = _score(txn, history, customer, trusted)
    return {"transaction": {k: txn[k] for k in ("id", "ts", "amount", "merchant", "country", "device_id")},
            **result}


@tool(agent="risk", description="Scan the customer's last 60 days of transactions and list the ones flagged as risky.")
def detect_anomalies(customer_id: str) -> dict:
    customer, history, trusted = _context(customer_id)
    flagged = []
    for txn in history:
        r = _score(txn, history, customer, trusted)
        if r["score"] >= FLAG_THRESHOLD:
            flagged.append({"id": txn["id"], "ts": txn["ts"], "amount": txn["amount"],
                            "merchant": txn["merchant"], "country": txn["country"], **r})
    flagged.sort(key=lambda x: -x["score"])
    return {"scanned": len(history), "flagged_count": len(flagged), "flagged": flagged[:10]}


@tool(agent="risk", description="List the devices/locations seen on the account and whether each is trusted.")
def get_device_location_info(customer_id: str) -> dict:
    devices = query(
        "SELECT device_id, label, city, country, last_seen, trusted FROM devices WHERE customer_id = ?",
        (customer_id,))
    return {"devices": devices, "untrusted_count": sum(1 for d in devices if not d["trusted"])}
