# Agent Design

## Flow

```
User Input
   |
   v
Intent Detection (classify_request -> Gemini, forced JSON via Pydantic schema)
   |
   v
Tool Selection (deterministic branch in agent.py, keyed on intent)
   |
   +-- knowledge_question --> search_knowledge_base
   +-- ticket_triage       --> search_knowledge_base
   +-- summarize_request   --> search_knowledge_base (top_k>1) --> summarize_text
   +-- create_task         --> create_task_object
   +-- cannot_answer       --> (no retrieval tool called)
   |
   v
Tool Execution
   |
   v
Response Generation
   (answer text is reused verbatim from KB content, or LLM-summarized
    strictly from retrieved KB content only - never freely generated)
   |
   v
Structured Output (validate_json_output checks the shape before returning)
   |
   v
Recommended Action
```

## 1. Intents supported

- `knowledge_question` - factual/how-to question, answerable from the KB.
- `ticket_triage` - user reporting a problem they're experiencing.
- `create_task` - user explicitly asking to open a task for a team.
- `summarize_request` - user wants a summary across one or more KB docs, not one specific fact.
- `cannot_answer` - out of scope for internal operations, or the KB has nothing relevant.

## 2. Tools available

| Tool | Type | Called for |
|---|---|---|
| `search_knowledge_base(query)` | Rule-based (TF-IDF cosine similarity) | knowledge_question, ticket_triage, summarize_request |
| `classify_request(user_input)` | LLM (Gemini) | Every request (runs first, always) |
| `create_task_object(user_input, ...)` | LLM (Gemini) | create_task |
| `summarize_text(query, docs)` | LLM (Gemini), grounded in already-retrieved docs only | summarize_request, when >=1 doc clears the score threshold |
| `validate_json_output(output)` | Rule-based | Internal QA gate before every response is returned |

## 3. How the agent chooses a tool

Tool selection is **deterministic Python branching on `intent`**, not
LLM-driven function calling. `classify_request` always runs first and
produces the intent; `agent.py`'s `run_agent()` then calls a fixed tool
sequence for that intent (see the flow diagram above).

This was a deliberate trade-off, not an oversight: deterministic routing
means the agent can never call the wrong tool for a given intent - the
only failure mode left is *classify_request assigning the wrong intent*,
which is a single, testable, isolated point of failure instead of two
compounding ones (intent AND tool choice). The cost is that the agent
can't discover a novel tool combination the developer didn't anticipate.
See `PROMPT_ENGINEERING.md` for the alternative (LLM-driven tool
selection via function calling) that was considered and not used here.

## 4. How the agent handles cases it can't answer

`KB_SCORE_THRESHOLD` (0.15, in `agent.py`) gates whether a TF-IDF match
is trusted. If the best match scores below the threshold, the agent
returns a fixed refusal message and reclassifies the case as
`cannot_answer` - it never calls an LLM to phrase an answer in this
path, so there is no LLM call in the loop that could invent one.

## 5. How the agent avoids answering outside the knowledge base

Two structural guardrails, not just prompt instructions:

1. For `knowledge_question` / `ticket_triage`, the `answer` field is the
   retrieved KB document's `content` column **verbatim** - the LLM is
   never asked to rephrase it, so it cannot quietly add an unsupported
   detail while paraphrasing.
2. For `summarize_request`, the LLM *is* asked to generate text (a
   summary across multiple docs can't be done by concatenation alone),
   but the prompt in `summarize_text()` restricts it to only the KB
   documents that already cleared `KB_SCORE_THRESHOLD`, and explicitly
   forbids adding information not present in those documents. This is a
   weaker guarantee than (1) - see `README.md` Limitations for the
   honest caveat about this.
