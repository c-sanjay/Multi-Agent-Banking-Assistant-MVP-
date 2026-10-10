"""Tools owned by the Credit / Loan agent (includes a tiny BM25 policy search = RAG layer)."""
import math
import re
from functools import lru_cache

from app import config
from app.db import query, query_one
from app.tools.registry import tool

MIN_CREDIT_SCORE = 650
MAX_FOIR = 0.50          # fixed-obligation-to-income ratio
MAX_LOAN_MULTIPLE = 24   # max personal loan = 24 x monthly income


def emi_formula(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12 / 100
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def _rate_for_score(score: int) -> float:
    return 10.5 if score >= 780 else 11.5 if score >= 740 else 12.5 if score >= 700 else 14.0


@tool(
    agent="credit",
    description="Calculate the monthly EMI for a loan. Pure maths; needs no customer data.",
    properties={
        "principal": {"type": "number", "description": "Loan amount in INR"},
        "annual_rate": {"type": "number", "description": "Annual interest rate in percent, e.g. 11"},
        "tenure_months": {"type": "integer", "description": "Tenure in months"},
    },
    required=["principal", "annual_rate", "tenure_months"],
)
def calculate_emi(customer_id: str, principal: float, annual_rate: float, tenure_months: int) -> dict:
    if principal <= 0 or tenure_months <= 0 or annual_rate < 0:
        return {"error": "principal and tenure must be positive and rate non-negative"}
    emi = emi_formula(principal, annual_rate, tenure_months)
    total = emi * tenure_months
    return {"principal": principal, "annual_rate": annual_rate, "tenure_months": tenure_months,
            "emi": round(emi, 2), "total_payable": round(total, 2), "total_interest": round(total - principal, 2)}


@tool(agent="credit", description="Get the customer's credit score (simulated credit bureau lookup).")
def get_credit_score(customer_id: str) -> dict:
    c = query_one("SELECT credit_score FROM customers WHERE id = ?", (customer_id,))
    if not c:
        return {"error": "customer not found"}
    s = c["credit_score"]
    band = "EXCELLENT" if s >= 780 else "GOOD" if s >= 720 else "FAIR" if s >= 650 else "POOR"
    return {"credit_score": s, "band": band, "bureau": "Simulated Bureau"}


@tool(agent="credit", description="List the customer's existing loans with outstanding balance, EMI and next due date.")
def get_loan_status(customer_id: str) -> dict:
    loans = query("SELECT id, loan_type, principal, annual_rate, emi, outstanding, status, next_due "
                  "FROM loans WHERE customer_id = ?", (customer_id,))
    return {"loan_count": len(loans), "loans": loans,
            "total_monthly_emi": sum(l["emi"] for l in loans if l["status"] == "ACTIVE")}


@tool(
    agent="credit",
    description="Check eligibility for a NEW personal loan using bank policy rules. Returns a decision with reasons.",
    properties={
        "amount": {"type": "number", "description": "Requested loan amount in INR"},
        "tenure_months": {"type": "integer", "description": "Requested tenure in months. Default 36."},
    },
    required=["amount"],
)
def check_loan_eligibility(customer_id: str, amount: float, tenure_months: int = 36) -> dict:
    c = query_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not c:
        return {"error": "customer not found"}
    existing_emi = sum(l["emi"] for l in query(
        "SELECT emi FROM loans WHERE customer_id = ? AND status = 'ACTIVE'", (customer_id,)))
    rate = _rate_for_score(c["credit_score"])
    new_emi = emi_formula(amount, rate, tenure_months)
    foir = (existing_emi + new_emi) / c["monthly_income"]
    max_amount = MAX_LOAN_MULTIPLE * c["monthly_income"]

    checks = [
        ("KYC verified", c["kyc_status"] == "VERIFIED", f"KYC status is {c['kyc_status']}"),
        (f"Credit score >= {MIN_CREDIT_SCORE}", c["credit_score"] >= MIN_CREDIT_SCORE,
         f"Credit score {c['credit_score']} is below {MIN_CREDIT_SCORE}"),
        (f"Obligations <= {int(MAX_FOIR * 100)}% of income", foir <= MAX_FOIR,
         f"Total EMIs would be {foir:.0%} of income (limit {MAX_FOIR:.0%})"),
        (f"Amount <= {MAX_LOAN_MULTIPLE}x monthly income", amount <= max_amount,
         f"Requested ₹{amount:,.0f} exceeds the cap of ₹{max_amount:,.0f}"),
    ]
    failed = [msg for _, ok, msg in checks if not ok]
    return {
        "eligible": not failed, "requested_amount": amount, "tenure_months": tenure_months,
        "indicative_rate": rate, "estimated_new_emi": round(new_emi, 2),
        "existing_monthly_emi": existing_emi, "monthly_income": c["monthly_income"],
        "foir_after_loan": round(foir, 3), "credit_score": c["credit_score"],
        "passed_checks": [name for name, ok, _ in checks if ok], "failed_checks": failed,
        "note": "Indicative only; final approval needs underwriting.",
    }


# ---------------------------------------------------------------- policy search (RAG)
def _tok(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@lru_cache(maxsize=1)
def _chunks() -> list[dict]:
    chunks = []
    for path in sorted(config.POLICY_DIR.glob("*.md")):
        for part in re.split(r"\n(?=## )", path.read_text(encoding="utf-8")):
            if part.strip():
                chunks.append({"source": path.name, "text": part.strip(), "tokens": _tok(part)})
    return chunks


def bm25_search(q: str, k: int = 2, k1: float = 1.5, b: float = 0.75) -> list[dict]:
    docs = _chunks()
    if not docs:
        return []
    avg = sum(len(d["tokens"]) for d in docs) / len(docs)
    scored = []
    for d in docs:
        s = 0.0
        for term in set(_tok(q)):
            df = sum(1 for x in docs if term in x["tokens"])
            if not df:
                continue
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            tf = d["tokens"].count(term)
            s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d["tokens"]) / avg))
        scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return [{"source": d["source"], "score": round(s, 2), "text": d["text"]} for s, d in scored[:k] if s > 0]


@tool(
    agent="credit",
    description="Search the bank's loan policy documents (eligibility rules, rates, documents needed, prepayment).",
    properties={"question": {"type": "string", "description": "What to look up in the policy docs"}},
    required=["question"],
)
def search_loan_policy(customer_id: str, question: str) -> dict:
    hits = bm25_search(question)
    return {"results": hits} if hits else {"results": [], "note": "No matching policy text found."}
