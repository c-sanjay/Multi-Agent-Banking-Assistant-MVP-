"""Streamlit chat UI with an agent-trace panel. Run: streamlit run ui/streamlit_app.py"""
import os
import uuid
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw

API_URL = os.getenv("API_URL", "http://localhost:8000")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


AI_AVATAR = load_avatar(str(PROJECT_ROOT / "aiprofile.png"), crop_fraction=0.72)
USER_AVATAR = load_avatar(str(PROJECT_ROOT / "userprofile.png"))

st.set_page_config(page_title="Multi-Agent Banking Assistant", page_icon="🏦", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background: linear-gradient(165deg, #171a33 0%, #202747 55%, #26385a 100%);
        border-right: 1px solid rgba(153, 190, 255, 0.22);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #eef3ff;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background: rgba(83, 104, 160, 0.24);
        border: 1px solid rgba(174, 196, 255, 0.28);
        border-radius: 12px;
        color: #f5f7ff;
        transition: background 120ms ease, border-color 120ms ease;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
        background: rgba(104, 133, 202, 0.42);
        border-color: rgba(190, 208, 255, 0.6);
        color: #ffffff;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: rgba(15, 20, 42, 0.82);
        border-color: rgba(174, 196, 255, 0.32);
        border-radius: 10px;
    }
    [class*="st-key-confirm_actions"] [data-testid="stBaseButton-primary"] {
        background: #16845b;
        border-color: #1b9a6a;
        color: #ffffff;
    }
    [class*="st-key-confirm_actions"] [data-testid="stBaseButton-primary"]:hover {
        background: #116b49;
        border-color: #16845b;
        color: #ffffff;
    }
    [class*="st-key-confirm_actions"] [data-testid="stBaseButton-secondary"] {
        background: rgba(127, 127, 127, 0.12);
        border-color: rgba(180, 190, 210, 0.32);
    }
    [class*="st-key-confirm_actions"] [data-testid="stBaseButton-secondary"]:hover {
        background: rgba(127, 127, 127, 0.22);
        border-color: rgba(180, 190, 210, 0.55);
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

EXAMPLES = {
    "💰 Balance + last 5 transactions": "Show my balance and last 5 transactions",
    "🕵️ Anything suspicious?": "Anything suspicious on my account?",
    "🏠 Loan eligibility (₹5 lakh)": "Am I eligible for a ₹5 lakh personal loan?",
    "🧮 EMI calculation": "Calculate EMI for ₹5L over 3 years at 11%",
    "🚨 Check ₹48,000 charge + block card": "That ₹48,000 charge looks wrong, check it and block my card",
    "📄 Prepayment policy": "What is the prepayment policy on personal loans?",
}


def api(method: str, path: str, **kw):
    try:
        r = requests.request(method, f"{API_URL}{path}", timeout=60, **kw)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        st.error(f"Backend error: {exc}. Is the API running at {API_URL}?")
        st.stop()


# ---------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("session_id", uuid.uuid4().hex[:12])
ss.setdefault("messages", [])      # [{"role", "content"}]
ss.setdefault("trace", None)
ss.setdefault("pending", None)
ss.setdefault("queued", None)

# ---------------------------------------------------------------- sidebar
customers = api("GET", "/customers")
labels = {f"{c['name']} ({c['id']}, {c['city']})": c["id"] for c in customers}
with st.sidebar:
    st.title("🏦 Banking Agents")
    choice = st.selectbox("Logged in as", list(labels))
    customer_id = labels[choice]
    if ss.get("customer_id") != customer_id:  # switching user starts a fresh conversation
        ss.update(customer_id=customer_id, session_id=uuid.uuid4().hex[:12], messages=[], trace=None, pending=None)

    health = api("GET", "/health")
    st.caption(f"LLM provider: **{health['llm_provider']}**")
    st.divider()
    st.subheader("Try a use case")
    for label, prompt in EXAMPLES.items():
        if st.button(label, use_container_width=True):
            ss.queued = prompt
    st.divider()
    if st.button("🔄 Reset demo data", use_container_width=True):
        api("POST", "/reset")
        ss.update(messages=[], trace=None, pending=None, session_id=uuid.uuid4().hex[:12])
        st.rerun()


def send(message: str) -> None:
    ss.messages.append({"role": "user", "content": message})
    data = api("POST", "/chat", json={"session_id": ss.session_id, "customer_id": ss.customer_id, "message": message})
    ss.messages.append({"role": "assistant", "content": data["answer"]})
    ss.trace, ss.pending = data["trace"], data["pending_confirmation"]


def confirm(approve: bool) -> None:
    data = api("POST", "/confirm", json={"session_id": ss.session_id, "customer_id": ss.customer_id, "approve": approve})
    ss.messages.append({"role": "assistant", "content": data["answer"]})
    ss.trace, ss.pending = data["trace"], None


# ---------------------------------------------------------------- input handling
typed = st.chat_input("Ask about your account, transactions, fraud, or loans…")
prompt = ss.queued or typed
ss.queued = None
if prompt:
    with st.spinner("Supervisor is routing your request…"):
        send(prompt)

# ---------------------------------------------------------------- layout
chat_col, trace_col = st.columns([3, 2], gap="large")

with chat_col:
    st.subheader("Chat")
    if not ss.messages:
        st.info("Pick a use case from the sidebar or type a question below.")
    for m in ss.messages:
        is_assistant = m["role"] == "assistant"
        with st.container(border=True):
            avatar_col, message_col = st.columns([0.65, 10], vertical_alignment="center")
            with avatar_col:
                st.image(AI_AVATAR if is_assistant else USER_AVATAR, width=40)
            with message_col:
                st.caption("Banking Assistant" if is_assistant else "You")
                st.markdown(m["content"])
    if ss.pending:
        st.warning(f"⚠️ Confirmation required: **{ss.pending['summary']}**")
        with st.container(key="confirm_actions"):
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirm", type="primary", use_container_width=True):
                confirm(True)
                st.rerun()
            if c2.button("✖ Cancel", use_container_width=True):
                confirm(False)
                st.rerun()

with trace_col:
    st.subheader("🔍 Agent trace")
    t = ss.trace
    if not t:
        st.caption("Routing decisions and tool calls will appear here.")
    else:
        if not t["guardrails"]["input_allowed"]:
            st.error(f"Blocked by guardrails: {t['guardrails']['reason']}")
        r = t.get("route")
        if r:
            st.markdown("**Supervisor routing**")
            st.write(" → ".join(f"`{a}`" for a in r["agents"]) or "—")
            st.caption(r["reasoning"])
        c1, c2, c3 = st.columns(3)
        c1.metric("LLM calls", t["llm_calls"])
        c2.metric("Tool calls", sum(len(a["tool_calls"]) for a in t["agent_runs"]))
        c3.metric("Latency", f"{t['total_latency_ms'] / 1000:.2f}s")
        for run in t["agent_runs"]:
            with st.expander(f"Agent: {run['agent']}  ·  {len(run['tool_calls'])} tool call(s)", expanded=True):
                for call in run["tool_calls"]:
                    st.markdown(f"🔧 `{call['tool']}` · {call['latency_ms']} ms")
                    if call["args"]:
                        st.json(call["args"], expanded=False)
                    with st.expander("result"):
                        st.json(call["result"], expanded=False)
        st.caption(f"request id: {t['request_id']}")
