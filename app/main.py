"""FastAPI backend (the 'API layer'). Run: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import config, supervisor
from app.data.seed import seed
from app.db import query, query_one

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not config.DB_PATH.exists():
        seed()
    yield


app = FastAPI(title="Multi-Agent Banking Assistant (MVP)", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    customer_id: str  # in a real system this comes from the auth token (OAuth2/OIDC), not the body
    message: str = Field(min_length=1, max_length=2000)


class ConfirmRequest(BaseModel):
    session_id: str
    customer_id: str
    approve: bool


def _check_customer(customer_id: str) -> None:
    if not query_one("SELECT id FROM customers WHERE id = ?", (customer_id,)):
        raise HTTPException(404, "Unknown customer")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": config.LLM_PROVIDER}


@app.get("/customers")
def customers() -> list[dict]:
    return query("SELECT id, name, city FROM customers ORDER BY id")


@app.get("/customer/{customer_id}/overview")
def customer_overview(customer_id: str) -> dict:
    _check_customer(customer_id)
    cust = query_one(
        "SELECT id, name, email, phone, city, home_country, monthly_income, credit_score, kyc_status "
        "FROM customers WHERE id = ?",
        (customer_id,),
    )
    acct = query_one(
        "SELECT account_no, account_type, balance, card_last4, card_status "
        "FROM accounts WHERE customer_id = ?",
        (customer_id,),
    )
    loans = query(
        "SELECT id, loan_type, principal, annual_rate, tenure_months, emi, outstanding, status, next_due "
        "FROM loans WHERE customer_id = ?",
        (customer_id,),
    )
    return {
        "customer": cust,
        "account": acct,
        "loans": loans or [],
    }


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    _check_customer(req.customer_id)
    return supervisor.handle_message(req.session_id, req.customer_id, req.message)


@app.post("/confirm")
def confirm(req: ConfirmRequest) -> dict:
    _check_customer(req.customer_id)
    return supervisor.confirm_action(req.session_id, req.customer_id, req.approve)


@app.post("/reset")
def reset() -> dict:
    """Demo helper: re-seed the database and clear sessions (e.g. to unblock the card again)."""
    seed()
    supervisor.SESSIONS.clear()
    return {"status": "reset"}
