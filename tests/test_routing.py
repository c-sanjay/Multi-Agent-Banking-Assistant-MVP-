from types import SimpleNamespace

from app import supervisor


def test_explicit_suspicious_charge_and_block_skips_router_llm(monkeypatch):
    def fail_if_called():
        raise AssertionError("Explicit high-confidence request should not call the router model.")

    monkeypatch.setattr(supervisor, "get_llm", fail_if_called)

    decision = supervisor.route("That ₹48,000 charge looks wrong, check it and block my card", history=[])
    assert decision["agents"] == ["risk", "customer"]
    assert decision["deterministic"] is True


def test_standard_account_request_uses_fast_path(monkeypatch):
    def fail_if_called():
        raise AssertionError("A clear account request should not call the router model.")

    monkeypatch.setattr(supervisor, "get_llm", fail_if_called)

    decision = supervisor.route("Show my balance and last 5 transactions", history=[])

    assert decision["agents"] == ["customer"]
    assert decision["deterministic"] is True


def test_unparseable_route_otherwise_falls_back_to_customer(monkeypatch):
    monkeypatch.setattr(
        supervisor,
        "get_llm",
        lambda: SimpleNamespace(complete=lambda **_: SimpleNamespace(text="not valid JSON")),
    )

    decision = supervisor.route("Can you help me with this?", history=[])

    assert decision["agents"] == ["customer"]
    assert decision["deterministic"] is False


def test_explicit_block_request_creates_confirmation_even_without_model_tool_call(monkeypatch):
    session_id = "test-explicit-card-block"
    supervisor.SESSIONS.pop(session_id, None)
    monkeypatch.setattr(supervisor, "get_llm", lambda: (_ for _ in ()).throw(
        AssertionError("The clear request should use the deterministic fast path.")
    ))

    reply = supervisor.handle_message(
        session_id,
        "C001",
        "That ₹48,000 charge looks wrong, check it and block my card",
    )

    assert reply["pending_confirmation"]["tool"] == "block_card"
    assert "confirm" in reply["answer"].lower()
    assert set(reply) == {"answer", "pending_confirmation", "blocked"}
    supervisor.SESSIONS.pop(session_id, None)
