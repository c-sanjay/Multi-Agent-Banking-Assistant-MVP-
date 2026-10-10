import json
from types import SimpleNamespace

from app import config
from app.llm import OpenRouterLLM


def test_openrouter_maps_tool_calls_and_results(monkeypatch):
    captured = {}
    response_data = {
        "choices": [{
            "message": {
                "content": "Your balance is available.",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "get_balance", "arguments": "{}"},
                }],
            },
        }],
    }

    def post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: response_data,
        )

    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/")
    monkeypatch.setattr("app.llm.requests.post", post)
    llm = OpenRouterLLM()

    result = llm.complete(
        system="Bank assistant",
        messages=[
            {"role": "user", "content": "Check my balance"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll check."},
                    {"type": "tool_use", "id": "call_0", "name": "get_balance", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "call_0",
                             "content": json.dumps({"balance_inr": 1000})}],
            },
        ],
        tools=[{
            "name": "get_balance",
            "description": "Get balance",
            "input_schema": {"type": "object", "properties": {}},
        }],
        model="test/model:free",
        max_tokens=123,
        purpose="agent:customer",
    )

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "test/model:free"
    assert captured["payload"]["max_tokens"] == 123
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "Bank assistant"}
    assert captured["payload"]["messages"][2]["tool_calls"][0]["function"] == {
        "name": "get_balance", "arguments": "{}",
    }
    assert captured["payload"]["messages"][3]["role"] == "tool"
    assert captured["payload"]["messages"][3]["tool_call_id"] == "call_0"
    assert captured["payload"]["tools"][0]["function"]["parameters"] == {
        "type": "object", "properties": {},
    }
    assert result.text == "Your balance is available."
    assert result.tool_calls[0].name == "get_balance"
    assert result.tool_calls[0].input == {}
    assert result.content_blocks[0]["type"] == "text"
    assert result.content_blocks[1]["type"] == "tool_use"
