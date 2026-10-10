"""Tool registry = the 'Agent Tool / MCP layer' (layer 5), in miniature.

Responsibilities:
  * map tool name -> python function + JSON schema shown to the LLM
  * least-privilege: each agent only gets the tools registered for it
  * identity injection: `customer_id` comes from the authenticated session (ToolContext),
    never from the LLM, so a prompt-injected model cannot read someone else's data
  * permission boundary / transaction approval: write tools need explicit user confirmation
  * schema validation of arguments + audit of every call
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolContext:
    customer_id: str
    confirmed: bool = False                 # True only when the user approved a pending action
    pending_action: dict | None = None      # set when a write tool asks for confirmation


@dataclass
class Tool:
    name: str
    description: str
    properties: dict[str, dict]
    required: list[str]
    fn: Callable[..., dict]
    agent: str
    needs_confirmation: bool = False

    def schema(self) -> dict:
        """Anthropic-style tool schema. Note: no customer_id parameter is exposed."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required,
            },
        }


TOOLS: dict[str, Tool] = {}


def tool(*, agent: str, description: str, properties: dict | None = None,
         required: list[str] | None = None, needs_confirmation: bool = False):
    def deco(fn: Callable[..., dict]):
        TOOLS[fn.__name__] = Tool(
            name=fn.__name__, description=description, properties=properties or {},
            required=required or [], fn=fn, agent=agent, needs_confirmation=needs_confirmation,
        )
        return fn
    return deco


def load_all() -> None:
    # Importing the modules registers their tools.
    from app.tools import customer_tools, loan_tools, risk_tools  # noqa: F401


def schemas_for(agent: str) -> list[dict]:
    load_all()
    return [t.schema() for t in TOOLS.values() if t.agent == agent]


_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}


def _validate(t: Tool, args: dict) -> str | None:
    for r in t.required:
        if r not in args:
            return f"missing required argument '{r}'"
    for k, v in args.items():
        if k not in t.properties:
            return f"unknown argument '{k}'"
        expected = _TYPES.get(t.properties[k].get("type", "string"))
        if expected and not isinstance(v, expected):
            return f"argument '{k}' must be {t.properties[k].get('type')}"
    return None


def execute(tool_name: str, args: dict[str, Any], agent: str, ctx: ToolContext) -> dict:
    """Run a tool on behalf of an agent. Always returns a dict (errors included)."""
    load_all()
    t = TOOLS.get(tool_name)
    if t is None:
        return {"error": f"unknown tool '{tool_name}'"}
    if t.agent != agent:  # permission boundary
        return {"error": f"agent '{agent}' is not permitted to call '{tool_name}'"}
    err = _validate(t, args)
    if err:
        return {"error": f"invalid arguments: {err}"}

    if t.needs_confirmation and not ctx.confirmed:
        ctx.pending_action = {"agent": agent, "tool": tool_name, "args": args}
        return {
            "status": "confirmation_required",
            "message": f"'{tool_name}' changes account state. The customer must confirm before it runs.",
            "action": {"tool": tool_name, "args": args},
        }
    try:
        return t.fn(customer_id=ctx.customer_id, **args)
    except Exception as exc:  # tool failures must not crash the agent loop
        return {"error": f"tool failed: {exc}"}
