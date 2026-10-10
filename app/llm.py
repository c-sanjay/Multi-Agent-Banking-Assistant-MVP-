"""Single wrapper around the LLM. Everything else in the app talks to `get_llm()`.

Two providers share one interface:
  * OpenRouterLLM: hosted models through OpenRouter's OpenAI-compatible API
  * AnthropicLLM : real tool-calling model (set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY)
  * MockLLM      : deterministic rule-based stand-in so the whole app runs offline / in tests

Messages use Anthropic-style content blocks:
  {"role": "user"|"assistant", "content": str | [ {"type": "text"|"tool_use"|"tool_result", ...} ]}
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests

from app import config


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    content_blocks: list[dict] = field(default_factory=list)  # to append to history as-is


class AnthropicLLM:
    def __init__(self) -> None:
        import anthropic
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (or use LLM_PROVIDER=mock).")
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 model: str, max_tokens: int = 1024, purpose: str = "") -> LLMResponse:
        kwargs = dict(model=model, system=system, messages=messages, max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
        resp = self.client.messages.create(**kwargs)
        out = LLMResponse()
        for block in resp.content:
            if block.type == "text":
                out.text += block.text
                out.content_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                out.tool_calls.append(ToolCall(block.id, block.name, dict(block.input)))
                out.content_blocks.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)})
        return out


class OpenRouterLLM:
    """OpenRouter's OpenAI-compatible chat-completions API, adapted to the app interface."""

    def __init__(self) -> None:
        if not config.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set (or switch to LLM_PROVIDER=mock).")

    @staticmethod
    def _messages(messages: list[dict]) -> list[dict]:
        converted = []
        for message in messages:
            content = message["content"]
            if isinstance(content, str):
                converted.append({"role": message["role"], "content": content})
            elif message["role"] == "assistant":
                text = "".join(block.get("text", "") for block in content
                               if block.get("type") == "text")
                tool_calls = [
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                    for block in content if block.get("type") == "tool_use"
                ]
                assistant_message = {"role": "assistant", "content": text or None}
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                converted.append(assistant_message)
            else:
                converted.extend(
                    {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": str(block["content"]),
                    }
                    for block in content if block.get("type") == "tool_result"
                )
        return converted

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 model: str, max_tokens: int = 1024, purpose: str = "") -> LLMResponse:
        request_messages = [{"role": "system", "content": system}, *self._messages(messages)]
        payload = {"model": model, "messages": request_messages, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = self._tools(tools)

        response = requests.post(
            f"{config.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                     "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenRouter returned a response without a chat completion.") from exc

        out = LLMResponse(text=message.get("content") or "")
        for call in message.get("tool_calls") or []:
            function = call["function"]
            try:
                arguments = json.loads(function["arguments"])
            except (KeyError, json.JSONDecodeError) as exc:
                raise RuntimeError("OpenRouter returned invalid JSON for a tool call.") from exc
            if not isinstance(arguments, dict):
                raise RuntimeError("OpenRouter tool-call arguments must be a JSON object.")
            tool_call = ToolCall(call["id"], function["name"], arguments)
            out.tool_calls.append(tool_call)
            out.content_blocks.append({
                "type": "tool_use", "id": tool_call.id, "name": tool_call.name,
                "input": tool_call.input,
            })
        if out.text:
            out.content_blocks.insert(0, {"type": "text", "text": out.text})
        return out


# --------------------------------------------------------------------------- mock LLM
def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def _parse_amount(text: str) -> float | None:
    t = text.lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|l\b|crore|cr\b|k\b)", t)
    if m:
        mult = {"lakh": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "cr": 1e7, "k": 1e3}[m.group(2)]
        return float(m.group(1)) * mult
    m = re.search(r"(?:₹|rs\.?\s*|inr\s*)(\d+(?:\.\d+)?)", t) or re.search(r"\b(\d{4,9})\b", t)
    return float(m.group(1)) if m else None


def _parse_months(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"(\d+)\s*(?:years?|yrs?|y\b)", t)
    if m:
        return int(m.group(1)) * 12
    m = re.search(r"(\d+)\s*months?", t)
    return int(m.group(1)) if m else None


def _parse_rate(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None


class MockLLM:
    """Keyword-driven fake model. Same interface, no network, no key.

    It exists so the architecture (routing, tool loop, guardrails, tracing, UI) can be run and
    tested end-to-end without an API key. Swap to AnthropicLLM for real language understanding.
    """

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 model: str = "", max_tokens: int = 1024, purpose: str = "") -> LLMResponse:
        if purpose == "route":
            return LLMResponse(text=json.dumps(self._route(self._last_user_text(messages))))
        if purpose == "compose":
            body = self._last_user_text(messages).split("\n\n[AGENT OUTPUTS]\n", 1)[-1]
            return LLMResponse(text=re.sub(r"^\[agent:\w+\]\n", "", body, flags=re.M))
        return self._agent_step(purpose.removeprefix("agent:"), messages)

    # -- helpers
    @staticmethod
    def _last_user_text(messages: list[dict]) -> str:
        for m in messages:
            if m["role"] == "user" and isinstance(m["content"], str):
                return m["content"]
        return ""

    def _route(self, text: str) -> dict:
        t = text.split("[CONTEXT]")[0].lower()
        risk = re.search(r"suspicious|fraud|wrong|unauthori[sz]ed|risk|anomal|scam|didn'?t make|not me|device|location", t)
        credit = re.search(r"loan|emi|eligib|credit score|interest|borrow|mortgage|prepay|foreclos", t)
        action = re.search(r"block|freeze|balance|profile|statement|account|card|transactions?|spent|spending", t)
        agents: list[str] = []
        if risk:
            agents.append("risk")
        if credit:
            agents.append("credit")
        if action and not credit and (not risk or re.search(r"block|freeze|balance|profile", t)):
            agents.append("customer")
        if not agents:
            agents = ["customer"]
        why = {"risk": "fraud/risk signals", "credit": "loan/credit question", "customer": "account information or action"}
        return {"agents": agents, "reasoning": "Matched " + ", ".join(why[a] for a in agents)}

    def _agent_step(self, agent: str, messages: list[dict]) -> LLMResponse:
        results = self._collect_results(messages)
        if results:  # second turn: compose an answer from tool output
            return LLMResponse(text=self._compose(agent, results))
        text = self._last_user_text(messages).split("[CONTEXT]")[0]
        calls = self._plan_tools(agent, text.lower(), text)
        blocks = [{"type": "tool_use", "id": f"mock_{i}", "name": n, "input": a} for i, (n, a) in enumerate(calls)]
        return LLMResponse(tool_calls=[ToolCall(b["id"], b["name"], b["input"]) for b in blocks],
                           content_blocks=blocks)

    @staticmethod
    def _collect_results(messages: list[dict]) -> dict[str, dict]:
        names, out = {}, {}
        for m in messages:
            if isinstance(m["content"], list):
                for b in m["content"]:
                    if b.get("type") == "tool_use":
                        names[b["id"]] = b["name"]
                    elif b.get("type") == "tool_result":
                        out[names[b["tool_use_id"]]] = json.loads(b["content"])
        return out

    def _plan_tools(self, agent: str, t: str, raw: str) -> list[tuple[str, dict]]:
        calls: list[tuple[str, dict]] = []
        if agent == "customer":
            if re.search(r"block|freeze", t):
                calls.append(("block_card", {"reason": "Customer requested block (suspected unauthorised activity)"
                                                   if re.search(r"wrong|fraud|suspicious|unauthori", t)
                                                   else "Customer requested card block"}))
            else:
                if "balance" in t:
                    calls.append(("get_balance", {}))
                if re.search(r"transaction|statement|spent|spending|last \d+", t):
                    n = re.search(r"(?:last|recent)\s+(\d+)", t)
                    calls.append(("get_transactions", {"limit": int(n.group(1)) if n else 5}))
                if re.search(r"profile|kyc|my details|who am i", t):
                    calls.append(("get_customer_profile", {}))
                if not calls:
                    calls = [("get_customer_profile", {}), ("get_balance", {})]
        elif agent == "risk":
            amt = _parse_amount(raw)
            tid = re.search(r"TXN-\d+", raw, re.I)
            if tid:
                calls.append(("score_transaction_risk", {"transaction_id": tid.group(0).upper()}))
            elif amt:
                calls.append(("score_transaction_risk", {"amount": amt}))
            else:
                calls.append(("detect_anomalies", {}))
            if re.search(r"device|location", t):
                calls.append(("get_device_location_info", {}))
        elif agent == "credit":
            amt, months, rate = _parse_amount(raw), _parse_months(raw), _parse_rate(raw)
            if "emi" in t and amt and (rate or months):
                calls.append(("calculate_emi", {"principal": amt, "annual_rate": rate or 11.0,
                                                "tenure_months": months or 36}))
            elif re.search(r"eligib|can i get|apply|qualify", t) and amt:
                calls.append(("check_loan_eligibility", {"amount": amt, "tenure_months": months or 36}))
            elif re.search(r"credit score|cibil", t):
                calls.append(("get_credit_score", {}))
            elif re.search(r"policy|document|prepay|foreclos|rate|tenure", t):
                calls.append(("search_loan_policy", {"question": raw}))
            else:
                calls.append(("get_loan_status", {}))
        return calls

    def _compose(self, agent: str, r: dict[str, dict]) -> str:
        parts: list[str] = []
        for name, d in r.items():
            if "error" in d:
                parts.append(f"I couldn't complete '{name}': {d['error']}")
            elif name == "get_balance":
                parts.append(f"Your {d['account_type'].lower()} account ({d['account_no_masked']}) has a balance of "
                             f"{_inr(d['balance_inr'])}. Card ending {d['card_last4']} is {d['card_status']}.")
            elif name == "get_transactions":
                rows = "\n".join(f"- {t['ts'][:10]} · {t['merchant']} · {_inr(t['amount'])} ({t['country']})"
                                 for t in d["transactions"])
                parts.append(f"Your last {d['count']} transactions:\n{rows}")
            elif name == "get_customer_profile":
                parts.append(f"{d['name']} ({d['customer_id']}), {d['city']}. KYC: {d['kyc_status']}. "
                             f"Registered phone {d['phone']}.")
            elif name == "block_card":
                if d.get("status") == "confirmation_required":
                    parts.append("I can block your debit card, but I need your confirmation first. "
                                 "Please confirm below (this action can't be undone online).")
                elif d.get("status") == "blocked":
                    parts.append(f"Your card ending {d['card_last4']} is now blocked.")
                else:
                    parts.append(f"Card ending {d.get('card_last4', '')} is already blocked.")
            elif name == "detect_anomalies":
                if not d["flagged_count"]:
                    parts.append(f"I scanned {d['scanned']} transactions and found nothing suspicious.")
                else:
                    rows = "\n".join(f"- {f['id']} · {_inr(f['amount'])} at {f['merchant']} ({f['country']}) · "
                                     f"risk {f['score']}/100 ({f['level']})" for f in d["flagged"][:5])
                    parts.append(f"I scanned {d['scanned']} transactions and flagged {d['flagged_count']}:\n{rows}")
            elif name == "score_transaction_risk":
                tx = d["transaction"]
                why = "\n".join(f"- {x}" for x in d["reasons"]) or "- No risk signals"
                parts.append(f"Transaction {tx['id']} ({_inr(tx['amount'])} at {tx['merchant']}) scores "
                             f"{d['score']}/100, risk level {d['level']}:\n{why}")
            elif name == "get_device_location_info":
                rows = "\n".join(f"- {x['label']} · {x['city']}, {x['country']} · "
                                 f"{'trusted' if x['trusted'] else 'NOT trusted'}" for x in d["devices"])
                parts.append(f"Devices seen on your account:\n{rows}")
            elif name == "calculate_emi":
                parts.append(f"For {_inr(d['principal'])} at {d['annual_rate']}% over {d['tenure_months']} months, "
                             f"your EMI is {_inr(d['emi'])}/month. Total payable {_inr(d['total_payable'])} "
                             f"(interest {_inr(d['total_interest'])}).")
            elif name == "check_loan_eligibility":
                if d["eligible"]:
                    parts.append(f"Good news: you look eligible for {_inr(d['requested_amount'])}. Indicative rate "
                                 f"{d['indicative_rate']}%, estimated EMI {_inr(d['estimated_new_emi'])}/month over "
                                 f"{d['tenure_months']} months. Your total obligations would be "
                                 f"{d['foir_after_loan']:.0%} of income. {d['note']}")
                else:
                    why = "\n".join(f"- {x}" for x in d["failed_checks"])
                    parts.append(f"You don't currently qualify for {_inr(d['requested_amount'])}:\n{why}")
            elif name == "get_credit_score":
                parts.append(f"Your credit score is {d['credit_score']} ({d['band']}).")
            elif name == "get_loan_status":
                if not d["loan_count"]:
                    parts.append("You have no active loans.")
                else:
                    rows = "\n".join(f"- {l['loan_type']} loan {l['id']}: outstanding {_inr(l['outstanding'])}, "
                                     f"EMI {_inr(l['emi'])}, next due {l['next_due']}" for l in d["loans"])
                    parts.append(f"Your loans:\n{rows}")
            elif name == "search_loan_policy":
                parts.append(d["results"][0]["text"].replace("## ", "") if d["results"]
                             else "I couldn't find that in the policy documents.")
        return "\n\n".join(parts)


_llm = None


def get_llm():
    global _llm
    if _llm is None:
        providers = {
            "openrouter": OpenRouterLLM,
            "anthropic": AnthropicLLM,
            "mock": MockLLM,
        }
        try:
            provider = providers[config.LLM_PROVIDER]
        except KeyError as exc:
            raise RuntimeError(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}") from exc
        _llm = provider()
    return _llm
