"""Light-weight AI Gateway (layer 3): input screening, PII masking on output, audit logging."""
import json
import re
import time

from app import config

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"reveal (your )?(system )?prompt",
    r"you are now",
    r"act as (an? )?(admin|developer|root)",
    r"another customer'?s?|other customer'?s?|someone else'?s? account",
    r"customer[_ ]?id\s*[:=]",
]

OFF_TOPIC_HINT = re.compile(r"\b(poem|recipe|joke|weather|cricket score|movie)\b", re.I)


def check_input(text: str) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    if len(text) > 1000:
        return False, "Message is too long. Please keep it under 1000 characters."
    for p in INJECTION_PATTERNS:
        if re.search(p, text, re.I):
            return False, ("I can only help with your own accounts, and I can't change my instructions "
                           "or access other customers' data.")
    if OFF_TOPIC_HINT.search(text):
        return False, "I'm a banking assistant. I can help with balances, transactions, fraud checks and loans."
    return True, ""


def mask_pii(text: str) -> str:
    """Mask long digit runs (card/account/Aadhaar-like) and full emails in anything shown to the user."""
    text = re.sub(r"\b(\d{4})[ -]?(\d{4})[ -]?(\d{4})[ -]?(\d{4})\b", r"**** **** **** \4", text)
    text = re.sub(r"\b\d{9,14}\b", lambda m: "*" * (len(m.group(0)) - 4) + m.group(0)[-4:], text)
    text = re.sub(r"\b([\w.])[\w.]*@([\w-]+\.[\w.]+)\b", r"\1***@\2", text)
    return text


def audit_log(record: dict) -> None:
    config.LOG_DIR.mkdir(exist_ok=True)
    record = {"logged_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}
    with open(config.LOG_DIR / "audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
