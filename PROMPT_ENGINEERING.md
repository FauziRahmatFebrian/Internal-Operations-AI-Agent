# Prompt Engineering

## Important note on architecture (read this first)

The study case's example prompt describes a **single agent prompt** where
the LLM itself is told about all available tools and decides which to
call (LLM-driven function calling / tool use).

This implementation does **not** do that. It uses **deterministic Python
routing** (see `AGENT_DESIGN.md`, point 3) with two separate,
narrower LLM prompts - one per LLM-backed tool (`classify_request` and
`create_task_object`/`summarize_text`). The consolidated prompt below is
provided because the brief asks for it explicitly and it documents the
*rules* the agent follows overall, but in the actual code those rules are
split across `_CLASSIFY_SYSTEM_PROMPT`, `_TASK_SYSTEM_PROMPT`, and
`_SUMMARIZE_SYSTEM_PROMPT` in `tools.py` - there is no single API call
where this whole prompt is sent as-is. Be ready to explain this
distinction in the technical discussion; claiming the consolidated
prompt below is literally what's sent to the API would be inaccurate.

## Consolidated reference prompt

```
You are an internal operations AI agent. Your job is to help internal
teams answer questions, classify user requests, summarize policy
documentation, and create simulated task objects.

You have access to these tools:
1. search_knowledge_base(query) - retrieves relevant internal documents.
2. classify_request(user_input) - determines intent, category, priority, confidence.
3. create_task_object(user_input, assigned_team, priority) - drafts a simulated task.
4. summarize_text(query, documents) - summarizes a set of already-retrieved documents.

Rules:
- Always classify the user input before deciding the final action.
- Use the knowledge base when the user asks for factual, policy-related,
  billing, account, technical, product, or data-related information.
- Do not answer using knowledge outside the retrieved documents.
- If the knowledge base does not contain enough information, say that you
  cannot answer based on the available knowledge base.
- Do not fabricate sources or invent document IDs.
- Always return valid JSON.
- Always include: user_input, intent, tools_used, result, confidence, and
  recommended_action.
```

## How this maps to the actual per-tool prompts

- **classify_request** (`_CLASSIFY_SYSTEM_PROMPT` in `tools.py`) implements
  rules 1, "role", and the intent/category/priority/confidence part of the
  output contract. It does NOT generate the final answer text - this is
  deliberate, so a bad answer can never leak out of the classification
  step.
- **create_task_object** (`_TASK_SYSTEM_PROMPT`) implements the
  no-fabrication rule scoped specifically to task drafting: "do not invent
  facts not stated or clearly implied by the user's message."
- **summarize_text** (`_SUMMARIZE_SYSTEM_PROMPT`) implements the
  KB-grounding and no-fabrication rules scoped to summarization: it is
  only ever given documents that already passed `KB_SCORE_THRESHOLD`, and
  is told to use only those documents.
- The overall JSON output contract (`user_input`, `intent`, `tools_used`,
  `result`, `confidence`, `recommended_action`) is enforced in **Python**,
  in `run_agent()`, not by an LLM prompt - `validate_json_output` checks it
  before every return.

## Why not one true agent prompt with function calling?

Considered and rejected for this 2-day case study, mainly for
evaluability: with deterministic routing, `evaluation.md`'s "predicted
intent" and "tools used" columns are explainable by reading `agent.py`'s
if/elif chain. With LLM-driven tool calling, a wrong tool call could stem
from an ambiguous user message, an ambiguous tool description, or the
model's own reasoning - three different failure modes to disentangle
during the 2-day window. This is a real trade-off, not a strictly better
choice - see `README.md` Limitations and "Ideas for Future Development".
