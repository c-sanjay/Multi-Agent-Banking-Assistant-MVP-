# Architecture and approach

## Goal and scoping
The reference diagram has nine layers. In 48 hours I built the thinnest vertical slice that still proves the
core idea: **an LLM supervisor that routes to specialist tool-using agents over simulated banking APIs, with
safety controls and visible traces.** Everything else is documented as future work.

## Request flow
1. **Guardrails** screen the message (length, prompt-injection patterns, off-topic).
2. **Supervisor** calls the LLM with the agent catalogue and gets back JSON
   `{"agents": [...], "reasoning": "..."}`. The output is parsed defensively: unknown names are dropped and
   an empty or invalid answer falls back to the customer agent.
3. Chosen agents run **sequentially** in a fixed order (risk → credit → customer), so an analysis agent's
   findings are passed as context to a later action agent.
4. Each agent runs a **tool-calling loop** (LLM → tool → result → LLM …, capped at 6 steps).
5. One agent: its answer is returned. Several: the supervisor LLM merges them into one reply.
6. PII is masked on output; the trace and an audit record are written.

## Why this design
| Decision | Reason |
|---|---|
| Supervisor + narrow agents instead of one big agent | Smaller prompts and toolsets are easier to test and make wrong tool use less likely. Each agent can use a cheaper model. |
| Routing via LLM returning JSON | Handles natural phrasing and multi-intent requests. Validation makes malformed output safe. |
| **Rule-based fraud scoring and eligibility; LLM only explains** | Decisions are deterministic, auditable and testable. The model cannot invent a risk score or approve a loan. |
| Customer identity injected by the backend (`ToolContext`) | The LLM never sees or supplies `customer_id`, so prompt injection cannot reach another customer's data. |
| Per-agent tool allow-list | Least privilege. The risk agent cannot call `block_card` even if the model tries. |
| Confirmation gate for write tools | `block_card` returns `confirmation_required` and stores a pending action. It runs only after the user clicks Confirm (or types "yes"). The confirmed execution is deterministic and does not go through the LLM. |
| Hallucination control | Prompts require answering only from tool results; tool errors are surfaced; numbers are computed by tools. |
| Trace panel | Makes routing and tool use visible for the demo and for debugging. |
| Single `llm.py` wrapper with an offline mock | Provider swap is one file; the app and tests run without an API key. |

## Safety summary
Input screening, PII masking on output, masked identifiers inside tools, argument validation, permission
boundary, human confirmation for state changes, step cap on agent loops, tool-result size cap, audit log.

## Trade-offs I would discuss
- Keyword-based guardrails are easy to bypass; production needs a classifier model and policy engine.
- Sequential agents add latency; independent agents could run in parallel.
- The router is one LLM call; a labelled routing eval set would let me measure accuracy and tune the prompt.
- In-memory sessions do not scale across processes; use Redis or a database.

## Next steps
Expose tools via an MCP server, add OAuth2 identity, run evals for routing and groundedness, stream responses,
add a notification agent, and add token/cost tracking per request.
