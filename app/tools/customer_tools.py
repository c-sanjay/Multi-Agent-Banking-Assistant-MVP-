"""Tools owned by the Customer / Banking agent."""
from app.db import execute, query, query_one
from app.tools.registry import tool


def _mask(value: str, keep: int = 4) -> str:
    return "*" * max(len(value) - keep, 0) + value[-keep:]


@tool(agent="customer", description="Get the customer's profile (name, city, KYC status, income band).")
def get_customer_profile(customer_id: str) -> dict:
    c = query_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not c:
        return {"error": "customer not found"}
    return {
        "customer_id": c["id"], "name": c["name"], "city": c["city"],
        "email": c["email"][0] + "***@" + c["email"].split("@")[1],
        "phone": _mask(c["phone"], 2), "kyc_status": c["kyc_status"],
        "monthly_income": c["monthly_income"],
    }


@tool(agent="customer", description="Get the current account balance and card status.")
def get_balance(customer_id: str) -> dict:
    a = query_one("SELECT * FROM accounts WHERE customer_id = ?", (customer_id,))
    if not a:
        return {"error": "account not found"}
    return {
        "account_no_masked": _mask(a["account_no"]), "account_type": a["account_type"],
        "balance_inr": a["balance"], "card_last4": a["card_last4"], "card_status": a["card_status"],
    }


@tool(
    agent="customer",
    description="Get the most recent transactions, newest first.",
    properties={"limit": {"type": "integer", "description": "How many transactions (1-20). Default 5."}},
)
def get_transactions(customer_id: str, limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 20))
    rows = query(
        "SELECT id, ts, amount, merchant, category, country, channel FROM transactions "
        "WHERE customer_id = ? ORDER BY ts DESC LIMIT ?", (customer_id, limit))
    return {"count": len(rows), "transactions": rows}


@tool(
    agent="customer",
    description=("Block the customer's debit card. This is a write action: the customer must "
                 "confirm before it executes, so call it only when the customer asked for it."),
    properties={"reason": {"type": "string", "description": "Why the card is being blocked."}},
    required=["reason"],
    needs_confirmation=True,
)
def block_card(customer_id: str, reason: str) -> dict:
    a = query_one("SELECT card_last4, card_status FROM accounts WHERE customer_id = ?", (customer_id,))
    if not a:
        return {"error": "account not found"}
    if a["card_status"] == "BLOCKED":
        return {"status": "already_blocked", "card_last4": a["card_last4"]}
    execute("UPDATE accounts SET card_status = 'BLOCKED' WHERE customer_id = ?", (customer_id,))
    return {"status": "blocked", "card_last4": a["card_last4"], "reason": reason}
