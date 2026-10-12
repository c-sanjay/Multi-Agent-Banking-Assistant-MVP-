"""Mira Banking Assistant - Modern Executive Fintech Chat UI.
Run: streamlit run ui/streamlit_app.py
"""
from __future__ import annotations

import base64
import os
import uuid
from io import BytesIO
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw

API_URL = os.getenv("API_URL", "http://localhost:8000")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "Logo.png"
USER_AVATAR_PATH = PROJECT_ROOT / "userprofile.png"


# ---------------------------------------------------------------- Avatar Utilities
@st.cache_data
def load_avatar(path: str, crop_fraction: float = 1.0) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    side = int(min(image.size) * crop_fraction)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    mask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((2, 2, 254, 254), fill=255)
    image.putalpha(mask)
    return image


@st.cache_data
def load_logo_avatar(path: str) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    image = image.crop((
        int(image.width * 0.19),
        int(image.height * 0.17),
        int(image.width * 0.46),
        int(image.height * 0.84),
    ))
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    mask = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(mask).ellipse((2, 2, 254, 254), fill=255)
    image.putalpha(mask)
    return image


AI_AVATAR = load_logo_avatar(str(LOGO_PATH))
USER_AVATAR = load_avatar(str(USER_AVATAR_PATH))

_logo_avatar_buffer = BytesIO()
AI_AVATAR.save(_logo_avatar_buffer, format="PNG")
LOGO_BASE64 = base64.b64encode(_logo_avatar_buffer.getvalue()).decode("ascii")

# ---------------------------------------------------------------- Page Config
st.set_page_config(
    page_title="Mira | Private Banking Assistant",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------- Design System CSS
CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap");

:root {
    --bg-main: #f8fafc;
    --navy-primary: #0a192f;
    --navy-surface: #0f2744;
    --navy-light: #1e3a5f;
    --accent-cyan: #0284c7;
    --accent-emerald: #059669;
    --accent-ruby: #e11d48;
    --accent-amber: #d97706;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --border-card: #e2e8f0;
    --shadow-soft: 0 10px 30px -5px rgba(10, 25, 47, 0.05), 0 4px 12px -2px rgba(10, 25, 47, 0.03);
    --shadow-elevated: 0 20px 45px -8px rgba(10, 25, 47, 0.08), 0 6px 16px -4px rgba(10, 25, 47, 0.03);
}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    color: var(--text-primary);
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 10% 8%, rgba(14, 165, 233, 0.07), transparent 32rem),
        radial-gradient(circle at 90% 15%, rgba(99, 102, 241, 0.05), transparent 30rem),
        linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    background-attachment: fixed;
}

[data-testid="stAppDeployButton"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
    display: none !important;
}
[data-testid="stMainMenu"] {
    visibility: hidden;
}
.block-container {
    padding: 1.2rem 1.6rem 2.2rem;
    max-width: 1100px;
}

/* ---------------- Top Navbar ---------------- */
[class*="st-key-top_navbar"] {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid var(--border-card);
    border-radius: 20px;
    padding: 0.65rem 1.3rem;
    margin-bottom: 1.2rem;
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(16px);
}
[class*="st-key-top_navbar"] [data-testid="stHorizontalBlock"] {
    align-items: center;
}

/* ---------------- Compact Sign-in Card ---------------- */
[class*="st-key-signin_compact_box"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff;
    border: 1px solid var(--border-card);
    border-radius: 24px !important;
    padding: 2.2rem 2.4rem !important;
    box-shadow: var(--shadow-elevated);
    text-align: center;
}
.signin-compact-title {
    font-size: 1.55rem;
    font-weight: 800;
    color: var(--navy-primary);
    margin: 0 0 0.25rem 0;
    letter-spacing: -0.025em;
}
.signin-compact-sub {
    font-size: 0.88rem;
    color: var(--text-muted);
    margin: 0 0 1.4rem 0;
    line-height: 1.5;
}
.persona-preview-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 0.85rem 1rem;
    text-align: left;
    margin: 0.9rem 0 1.2rem;
}
.persona-preview-tag {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 0.18rem 0.52rem;
    border-radius: 999px;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 0.35rem;
}
.persona-preview-desc {
    font-size: 0.78rem;
    color: var(--text-secondary);
    line-height: 1.45;
}
.signin-badge-strip {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 1.2rem;
}
.signin-feature-pill {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #475569;
    padding: 0.22rem 0.6rem;
}

/* ---------------- Chat Stream Container ---------------- */
[class*="st-key-chat_panel_wrapper"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff;
    border: 1px solid var(--border-card);
    border-radius: 24px !important;
    padding: 1.3rem 1.6rem;
    box-shadow: var(--shadow-elevated);
}
.chat-header-row {
    margin-bottom: 0.9rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #f1f5f9;
}
.chat-header-title {
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--navy-primary);
    margin: 0;
}
.chat-header-subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0.15rem 0 0 0;
}

/* Chat Messages */
[data-testid="stChatMessage"] {
    border-radius: 18px !important;
    padding: 0.95rem 1.2rem !important;
    margin-bottom: 0.8rem !important;
    box-shadow: 0 3px 12px rgba(10, 25, 47, 0.035);
    animation: message-slide-in 220ms ease-out both;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
    border: 1px solid #cbd5e1 !important;
    color: var(--navy-primary) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    color: #1e293b !important;
}
[data-testid="stChatMessage"] p {
    font-size: 0.95rem;
    line-height: 1.68;
    margin-bottom: 0.35rem;
}
[data-testid="stChatMessage"] code {
    font-family: "JetBrains Mono", monospace !important;
    background: #f1f5f9;
    padding: 0.15rem 0.35rem;
    border-radius: 5px;
    font-size: 0.88rem;
    color: #0284c7;
}
@keyframes message-slide-in {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Welcome Hero in Chat */
.welcome-hero {
    border-radius: 20px;
    background:
        radial-gradient(circle at 50% 0%, rgba(2, 132, 199, 0.08), transparent 70%),
        linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid #e2e8f0;
    padding: 2.2rem 1.8rem;
    text-align: center;
    box-shadow: var(--shadow-soft);
    margin: 0.3rem 0 0.9rem;
}
.welcome-logo-circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(10, 25, 47, 0.12);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 0.9rem;
    padding: 6px;
    border: 2px solid #e0f2fe;
}
.welcome-hero-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--navy-primary);
    margin-bottom: 0.35rem;
    letter-spacing: -0.02em;
}
.welcome-hero-desc {
    font-size: 0.9rem;
    color: var(--text-muted);
    max-width: 520px;
    margin: 0 auto 1.4rem;
    line-height: 1.6;
}
.starter-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    text-align: left;
}
.starter-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 0.85rem 1rem;
    box-shadow: 0 2px 8px rgba(10, 25, 47, 0.03);
}
.starter-card strong {
    display: block;
    font-size: 0.84rem;
    color: var(--navy-primary);
    margin-bottom: 0.15rem;
}
.starter-card span {
    font-size: 0.74rem;
    color: var(--text-muted);
    line-height: 1.4;
    display: block;
}

/* ---------------- High-Security Confirmation Box ---------------- */
.security-alert-box {
    background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    border: 1.5px solid #f97316;
    border-radius: 18px;
    padding: 1.25rem 1.4rem;
    margin: 0.7rem 0;
    box-shadow: 0 10px 25px -4px rgba(249, 115, 22, 0.15);
}
.security-alert-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.96rem;
    font-weight: 800;
    color: #9a3412;
    margin-bottom: 0.45rem;
}
.security-alert-body {
    font-size: 0.88rem;
    color: #7c2d12;
    line-height: 1.55;
    margin-bottom: 0.85rem;
}

/* Chat Input Styling */
[data-testid="stChatInput"] {
    border-radius: 18px !important;
    border: 1.5px solid #cbd5e1 !important;
    background: #ffffff !important;
    box-shadow: 0 6px 20px rgba(10, 25, 47, 0.06) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #0284c7 !important;
    box-shadow: 0 8px 24px rgba(2, 132, 199, 0.14) !important;
}

/* ---------------- Prompt Hub Pills ---------------- */
.prompt-hub-title {
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--navy-primary);
    margin: 0.75rem 0 0.35rem;
}
[class*="st-key-prompt_btn"] button {
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    background: #f8fafc !important;
    color: #1e293b !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    padding: 0.48rem 0.7rem !important;
    transition: all 0.18s ease !important;
}
[class*="st-key-prompt_btn"] button:hover {
    border-color: #0284c7 !important;
    background: #f0f9ff !important;
    color: #0284c7 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 14px rgba(2, 132, 199, 0.08) !important;
}

/* Typing Indicator Animation */
.typing-bubble {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 0.65rem 1rem;
    border-radius: 16px;
    color: var(--navy-light);
    font-size: 0.86rem;
    font-weight: 600;
}
.dot-flashing {
    display: flex;
    gap: 4px;
}
.dot-flashing span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #0284c7;
    animation: bounce 1.3s infinite ease-in-out;
}
.dot-flashing span:nth-child(2) { animation-delay: 0.16s; }
.dot-flashing span:nth-child(3) { animation-delay: 0.32s; }
@keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30% { transform: translateY(-5px); opacity: 1; }
}

/* Footer Note */
.app-footer {
    text-align: center;
    font-size: 0.74rem;
    color: #94a3b8;
    margin-top: 1.5rem;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- Prompt Dictionary
PROMPTS = {
    "Popular ⚡": [
        ("Balance & 5 Txns", "Show my balance and last 5 transactions"),
        ("Suspicious Activity Scan", "Anything suspicious on my account?"),
        ("Loan Eligibility Check", "Am I eligible for a ₹5 lakh personal loan?"),
        ("Dispute & Block Card", "That ₹48,000 charge looks wrong, check it and block my card"),
    ],
    "Fraud & Risk ": [
        ("Scan Anomalies", "Anything suspicious on my account?"),
        ("Score Specific Charge", "Why was that ₹48,000 charge flagged as suspicious?"),
        ("Freeze Compromised Card", "Please block my debit card immediately"),
        ("Review Unknown Devices", "Are there any unrecognised devices linked to my profile?"),
    ],
    "Loans & Credit ": [
        ("Loan Eligibility", "Am I eligible for a ₹5 lakh personal loan?"),
        ("EMI Calculator (₹5L, 3y, 11%)", "Calculate EMI for ₹5L over 3 years at 11%"),
        ("Check Credit Score", "What is my credit score and what does it mean?"),
        ("Existing Loan Details", "What is the status of my existing loan and next EMI due date?"),
    ],
    "Policy & Rules ": [
        ("Loan Prepayment Rules", "What is the prepayment policy on personal loans?"),
        ("Loan Documentation", "What documents are required for a personal loan approval?"),
        ("Dispute Liability Policy", "What is the policy for reporting unauthorized transactions?"),
    ],
}

PERSONA_METADATA = {
    "C001": {
        "tag": " Planted Fraud Anomaly",
        "tag_style": "background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5;",
        "scenario": "Includes planted ₹48k luxury watch transaction at 3 AM from an unknown device and card-testing patterns. Best for testing anomaly scanning and card freeze confirmation.",
    },
    "C002": {
        "tag": "Active Loan & Policy Search",
        "tag_style": "background:#ecfdf5; color:#047857; border:1px solid #a7f3d0;",
        "scenario": "Holds an active ₹3L Personal Loan. Best for testing EMI schedules, prepayment clauses, and policy RAG search.",
    },
    "C003": {
        "tag": "Loan Eligibility Denial",
        "tag_style": "background:#fef3c7; color:#b45309; border:1px solid #fde68a;",
        "scenario": "Income ₹45k and CIBIL score 612. Demonstrates underwriting denial explanations and deterministic EMI calculations.",
    },
    "C004": {
        "tag": "Prime Wealth Portfolio",
        "tag_style": "background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;",
        "scenario": "Executive income (₹2.0L/mo, CIBIL 815) with an active Car Loan. Demonstrates highest credit tier evaluation.",
    },
    "C005": {
        "tag": " KYC Pending Profile",
        "tag_style": "background:#f5f3ff; color:#6d28d9; border:1px solid #ddd6fe;",
        "scenario": "Account with pending verification status. Demonstrates KYC compliance notices and requirements.",
    },
}


# ---------------------------------------------------------------- API Client
def api(method: str, path: str, **kw):
    try:
        r = requests.request(method, f"{API_URL}{path}", timeout=60, **kw)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        st.error(f"⚠️ **Backend Unavailable**: Could not connect to FastAPI at `{API_URL}` ({exc}). "
                 f"Ensure `python run.py` or `uvicorn app.main:app` is running.")
        st.stop()


def queue_prompt(prompt_text: str) -> None:
    ss.queued = prompt_text


def send_chat(message: str) -> None:
    data = api("POST", "/chat", json={"session_id": ss.session_id, "customer_id": ss.customer_id, "message": message})
    ss.messages.append({"role": "assistant", "content": data["answer"]})
    ss.pending = data.get("pending_confirmation")
    ss.overview = api("GET", f"/customer/{ss.customer_id}/overview")


def handle_confirm(approve: bool) -> None:
    data = api("POST", "/confirm", json={"session_id": ss.session_id, "customer_id": ss.customer_id, "approve": approve})
    ss.messages.append({"role": "assistant", "content": data["answer"]})
    ss.pending = None
    ss.overview = api("GET", f"/customer/{ss.customer_id}/overview")


def reset_customer_session() -> None:
    ss.update(messages=[], pending=None, queued=None, session_id=uuid.uuid4().hex[:12])


# ---------------------------------------------------------------- State Initialization
ss = st.session_state
ss.setdefault("signed_in", False)
ss.setdefault("customer_id", None)
ss.setdefault("session_id", uuid.uuid4().hex[:12])
ss.setdefault("messages", [])
ss.setdefault("pending", None)
ss.setdefault("queued", None)
ss.setdefault("overview", None)

customers = api("GET", "/customers")
customer_options = {
    f"{c['name']} ({c['id']}, {c['city']})": c["id"]
    for c in customers
}

# ---------------------------------------------------------------- COMPACT SIGN-IN SCREEN
if not ss.signed_in:
    _, signin_card, _ = st.columns([1, 1.8, 1])
    with signin_card:
        with st.container(border=True, key="signin_compact_box"):
            st.image(str(LOGO_PATH), width=210)
            st.markdown(
                '<h2 class="signin-compact-title">Welcome to Mira</h2>'
                '<p class="signin-compact-sub">Autonomous Multi-Agent Banking Assistant with specialist '
                'routing, risk heuristics, and human-in-the-loop protection.</p>',
                unsafe_allow_html=True,
            )

            # Persona Selector Dropdown
            selected_label = st.selectbox(
                "Select Customer Persona",
                options=list(customer_options.keys()),
                index=0,
                label_visibility="collapsed",
            )
            chosen_id = customer_options[selected_label]
            meta = PERSONA_METADATA.get(chosen_id, {"tag": "Demo Profile", "tag_style": "", "scenario": "Simulated banking customer."})

            # Compact Scenario Preview
            st.markdown(
                f'<div class="persona-preview-box">'
                f'  <span class="persona-preview-tag" style="{meta["tag_style"]}">{meta["tag"]}</span>'
                f'  <div class="persona-preview-desc">{meta["scenario"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if st.button("Sign in to Assistant →", type="primary", use_container_width=True):
                ss.customer_id = chosen_id
                ss.signed_in = True
                reset_customer_session()
                ss.overview = api("GET", f"/customer/{chosen_id}/overview")
                st.rerun()

            st.markdown(
                '<div class="signin-badge-strip">'
                '<span class="signin-feature-pill"> Hybrid Routing</span>'
                '<span class="signin-feature-pill"> Injected Identity</span>'
                '<span class="signin-feature-pill"> Confirmation Gate</span>'
                '</div>'
                '<div class="app-footer">Demo Experience · Isolated SQLite Environment</div>',
                unsafe_allow_html=True,
            )
    st.stop()


# ---------------------------------------------------------------- MAIN APPLICATION VIEW
if not ss.overview or ss.overview.get("customer", {}).get("id") != ss.customer_id:
    ss.overview = api("GET", f"/customer/{ss.customer_id}/overview")

me = ss.overview["customer"]
acct = ss.overview["account"]
loans = ss.overview.get("loans", [])
card_status = acct.get("card_status", "ACTIVE")
card_last4 = acct.get("card_last4", "0000")
bal_formatted = f"₹{acct.get('balance', 0):,.2f}"

# Top Navbar with brand and customer profile
with st.container(key="top_navbar"):
    nb_brand, nb_user = st.columns([3, 1], vertical_alignment="center")
    with nb_brand:
        st.image(str(LOGO_PATH), width=180)
    with nb_user:
        with st.popover(f"👤 {me['name']} ({me['id']})", use_container_width=True):
            st.markdown(f"**{me['name']}**")
            st.caption(f"Customer ID: `{me['id']}` · {me['city']}, {me['home_country']}")
            st.caption(f"Account: `•••• {acct.get('account_no', '')[-4:]}` · Balance: **{bal_formatted}**")
            st.caption(f"Card: `•••• {card_last4}` ({card_status})")
            st.caption(f"Credit Score: `{me.get('credit_score')}` · KYC: `{me.get('kyc_status')}`")
            st.divider()
            if st.button("Reset Demo State", use_container_width=True, help="Re-seeds mock database and unblocks cards"):
                api("POST", "/reset")
                reset_customer_session()
                ss.overview = api("GET", f"/customer/{ss.customer_id}/overview")
                st.toast("Database re-seeded! Cards unblocked.", icon="✅")
                st.rerun()
            if st.button(" Clear Chat History", use_container_width=True):
                reset_customer_session()
                st.rerun()
            if st.button(" Sign Out / Switch Customer", use_container_width=True):
                ss.signed_in = False
                ss.customer_id = None
                ss.overview = None
                reset_customer_session()
                st.rerun()

# Clean, Focused Chat Stream Container
with st.container(border=True, key="chat_panel_wrapper"):
    # Header Row
    st.markdown(
        f'<div class="chat-header-row">'
        f'  <div>'
        f'    <h2 class="chat-header-title">Good day, {me["name"]} 👋</h2>'
        f'    <p class="chat-header-subtitle">How can Mira assist with your everyday banking and security today?</p>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Dynamic Chat Slot
    chat_container = st.container(height=520, border=False)

    # Render Chat History
    with chat_container:
        if not ss.messages and not ss.pending:
            st.markdown(
                '<div class="welcome-hero">'
                f'<div class="welcome-logo-circle"><img src="data:image/png;base64,{LOGO_BASE64}" width="46"></div>'
                '<div class="welcome-hero-title">Mira Banking Assistant Ready</div>'
                '<div class="welcome-hero-desc">Ask anything about your account balances, recent transactions, '
                'security alerts, personal loan eligibility, or lending policies.</div>'
                '<div class="starter-grid">'
                '  <div class="starter-card"><strong> Everyday Banking</strong><span>Balances, statements, card actions</span></div>'
                '  <div class="starter-card"><strong> Fraud & Risk Sentinel</strong><span>Scan transactions and suspicious activity</span></div>'
                '  <div class="starter-card"><strong> Lending & Credit</strong><span>Deterministic EMI math & eligibility</span></div>'
                '  <div class="starter-card"><strong> Loan Policies</strong><span>RAG retrieval over bank policy documents</span></div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        for m in ss.messages:
            if m["role"] == "user":
                with st.chat_message("user", avatar=USER_AVATAR):
                    st.markdown(m["content"])
            else:
                with st.chat_message("assistant", avatar=AI_AVATAR):
                    st.markdown(m["content"])

        # Render Pending Confirmation Gate
        if ss.pending:
            with st.chat_message("assistant", avatar=AI_AVATAR):
                st.markdown(
                    f'<div class="security-alert-box">'
                    f'<div class="security-alert-header"> High-Security Action: Explicit Confirmation Required</div>'
                    f'<div class="security-alert-body">'
                    f'  <strong>Action:</strong> {ss.pending["summary"]}<br>'
                    f'  <strong>Target:</strong> Debit Card ending in •••• {card_last4}<br>'
                    f'  <em>This write operation will immediately freeze card activity to protect against unauthorized transactions.</em>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                cf_col1, cf_col2 = st.columns(2)
                with cf_col1:
                    if st.button(" Confirm & Execute Action", type="primary", use_container_width=True, key="btn_confirm_yes"):
                        handle_confirm(True)
                        st.rerun()
                with cf_col2:
                    if st.button("✕ Cancel Request", use_container_width=True, key="btn_confirm_no"):
                        handle_confirm(False)
                        st.rerun()

    # Categorized Quick Action Prompt Hub
    st.markdown('<div class="prompt-hub-title">Suggested Requests & Shortcuts</div>', unsafe_allow_html=True)
    tab_labels = list(PROMPTS.keys())
    active_tabs = st.tabs(tab_labels)

    for tab_idx, tab_name in enumerate(tab_labels):
        with active_tabs[tab_idx]:
            p_items = PROMPTS[tab_name]
            p_cols = st.columns(len(p_items), gap="small")
            for item_idx, (btn_title, prompt_text) in enumerate(p_items):
                with p_cols[item_idx]:
                    with st.container(key=f"prompt_btn_{tab_idx}_{item_idx}"):
                        st.button(
                            btn_title,
                            use_container_width=True,
                            on_click=queue_prompt,
                            args=(prompt_text,),
                            help=f"Ask: \"{prompt_text}\"",
                            key=f"q_btn_{tab_idx}_{item_idx}",
                        )

    # Chat Input
    typed = st.chat_input("Ask Mira about your balance, suspicious activity, loan eligibility, or EMI...")

# ---------------------------------------------------------------- Chat Processing Trigger
prompt_to_send = ss.queued or typed
ss.queued = None

if prompt_to_send:
    ss.messages.append({"role": "user", "content": prompt_to_send})
    with chat_container:
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt_to_send)
        with st.chat_message("assistant", avatar=AI_AVATAR):
            st.markdown(
                '<div class="typing-bubble"><span>Mira is coordinating specialist agents</span>'
                '<div class="dot-flashing"><span></span><span></span><span></span></div></div>',
                unsafe_allow_html=True,
            )
    send_chat(prompt_to_send)
    st.rerun()

st.markdown(
    '<div class="app-footer">'
    'Mira Multi-Agent Banking Assistant · Protected by Injected Identity & Tool Confirmation Boundary · PII Masked'
    '</div>',
    unsafe_allow_html=True,
)
