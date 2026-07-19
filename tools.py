"""
tools.py - Tool implementations for the Internal Operations AI Agent.

Each tool is a standalone function so it can be tested in isolation
(see the __main__ block at the bottom) before being wired into
agent.py's orchestration logic.

Design choice: search_knowledge_base is RULE-BASED (TF-IDF cosine
similarity), not LLM-based. It can only ever return documents that
literally exist in knowledge_base.csv, which is the main structural
defense against hallucinated answers - the LLM is never asked to
"remember" KB content, only to phrase an answer using content we
already retrieved deterministically.
"""
import os
from typing import Literal, Optional
from dotenv import load_dotenv
load_dotenv()  
import pandas as pd
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
from google.genai import types

# Gemini client setup

_client: Optional[genai.Client] = None
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and fill "
                "it in, or export GEMINI_API_KEY in your shell."
            )
        _client = genai.Client(api_key=api_key)
    return _client


# Pydantic schemas -> forces Gemini to return structured, validated JSON
class ClassificationResult(BaseModel):
    intent: Literal[
        "knowledge_question",
        "ticket_triage",
        "create_task",
        "summarize_request",
        "cannot_answer",
    ]
    category: Literal[
        "Account Access",
        "Billing",
        "Technical Issue",
        "Product Question",
        "Data Request",
        "General Inquiry",
    ]
    priority: Literal["Low", "Medium", "High"]
    confidence: Literal["low", "medium", "high"]


class TaskObject(BaseModel):
    title: str
    assigned_team: str
    priority: Literal["Low", "Medium", "High"]
    description: str


class SummaryResult(BaseModel):
    summary: str


# ---------------------------------------------------------------------------
# Tool 1: search_knowledge_base(query)
# ---------------------------------------------------------------------------
_KB_PATH = os.path.join(os.path.dirname(__file__), "data", "knowledge_base.csv")
_kb_df = None
_vectorizer = None
_kb_matrix = None


def _load_kb():
    global _kb_df, _vectorizer, _kb_matrix
    if _kb_df is None:
        _kb_df = pd.read_csv(_KB_PATH)
        corpus = (_kb_df["title"] + ". " + _kb_df["content"]).tolist()
        _vectorizer = TfidfVectorizer(stop_words="english")
        _kb_matrix = _vectorizer.fit_transform(corpus)
    return _kb_df, _vectorizer, _kb_matrix


def search_knowledge_base(query: str, top_k: int = 3) -> dict:
    """ Score is TF-IDF cosine similarity in [0, 1]. Documents with a score
    of 0 (no lexical overlap at all) are dropped rather than returned
    as weak matches.
    """
    df, vectorizer, matrix = _load_kb()
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()
    top_idx = scores.argsort()[::-1][:top_k]

    results = []
    for i in top_idx:
        if scores[i] <= 0:
            continue
        row = df.iloc[i]
        results.append(
            {
                "doc_id": row["doc_id"],
                "title": row["title"],
                "content": row["content"],
                "score": round(float(scores[i]), 4),
            }
        )

    return {"tool_name": "search_knowledge_base", "results": results}


# ---------------------------------------------------------------------------
# Tool 2: classify_request(user_input)
# ---------------------------------------------------------------------------
_CLASSIFY_SYSTEM_PROMPT = """You are an internal operations request classifier.

Classify the user's message into exactly one of these intents:
- knowledge_question: user is asking a factual/how-to question that might be answered from a knowledge base.
- ticket_triage: user is reporting a problem or issue they are personally experiencing.
- create_task: user is explicitly asking to create/open a task or ticket for a team to act on.
- summarize_request: user is asking for a summary of policy/documentation, not asking one specific question.
- cannot_answer: the request is unrelated to internal operations (account, billing, technical, product, data, general company topics), or asks for something no internal knowledge base would plausibly contain (e.g. a colleague's personal data, external facts unrelated to the company).

Also assign:
- category: the operational category the request belongs to.
- priority: how urgent this seems (Low/Medium/High). Login, security, or fully-blocking issues are usually High.
- confidence: how confident you are in this classification (low/medium/high).

Return ONLY the structured fields requested. Do not try to answer the user's
question here - that happens in a separate step using the knowledge base."""


def classify_request(user_input: str) -> dict:
    client = get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=user_input,
        config=types.GenerateContentConfig(
            system_instruction=_CLASSIFY_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ClassificationResult,
            temperature=0.1,
        ),
    )
    parsed: ClassificationResult = response.parsed
    result = parsed.model_dump()
    result["tool_name"] = "classify_request"
    return result


# ---------------------------------------------------------------------------
# Tool 3: create_task_object(user_input, assigned_team, priority)
# ---------------------------------------------------------------------------
_TASK_SYSTEM_PROMPT = """You turn an internal operations request into a short,
actionable SIMULATED task object for a human team to review later. This task
is never sent to any real system - it is a draft for a human to check.

Do not invent facts that are not stated or clearly implied by the user's
message. Keep the description factual and grounded only in what the user
actually said."""


def create_task_object(
    user_input: str,
    assigned_team: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict:
    client = get_client()
    hint = ""
    if assigned_team:
        hint += f" Use assigned_team='{assigned_team}' unless the message clearly implies a different team."
    if priority:
        hint += f" Use priority='{priority}' unless the message clearly implies a different urgency."
    contents = user_input
    if hint:
        contents += "\n\n[Extraction hint, not part of the user's message]" + hint
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_TASK_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=TaskObject,
            temperature=0.1,
        ),
    )
    parsed: TaskObject = response.parsed
    return {
        "tool_name": "create_task_object",
        "task": parsed.model_dump(),
        "status": "simulated",
    }


# ---------------------------------------------------------------------------
# Optional tool: summarize_text(query, documents)
# ---------------------------------------------------------------------------
_SUMMARIZE_SYSTEM_PROMPT = """You summarize internal documentation for an
employee. You will be given a user question and one or more retrieved
documents. Write a short summary (2-4 sentences) that answers the
question using ONLY the information in the provided documents.

Do not add facts, numbers, or policy details that are not present in the
documents. If the documents don't fully answer the question, summarize
what they do say and note the gap - do not fill it with outside
knowledge."""


def summarize_text(query: str, documents: list) -> dict:
    client = get_client()
    doc_block = "\n\n".join(
        f"[{d['doc_id']}] {d['title']}: {d['content']}" for d in documents
    )
    contents = f"User question: {query}\n\nDocuments:\n{doc_block}"
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_SUMMARIZE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=SummaryResult,
            temperature=0.1,
        ),
    )
    parsed: SummaryResult = response.parsed
    return {
        "tool_name": "summarize_text",
        "summary": parsed.summary,
        "sources": [{"doc_id": d["doc_id"], "title": d["title"]} for d in documents],
    }


# Optional tool: validate_json_output(output)
_REQUIRED_KEYS = {
    "user_input": str,
    "intent": str,
    "tools_used": list,
    "result": dict,
    "confidence": str,
    "recommended_action": str,
}


def validate_json_output(output: dict) -> dict:
    """Optional tool. Checks that a final agent response has the required
    shape. Returns {"tool_name", "valid", "errors"} - does not raise, so
    callers can decide whether a validation failure should be fatal.
    """
    errors = []
    for key, expected_type in _REQUIRED_KEYS.items():
        if key not in output:
            errors.append(f"missing key: {key}")
        elif not isinstance(output[key], expected_type):
            errors.append(
                f"key '{key}' should be {expected_type.__name__}, got {type(output[key]).__name__}"
            )
    return {
        "tool_name": "validate_json_output",
        "valid": len(errors) == 0,
        "errors": errors,
    }


# Manual isolated test - run `python tools.py` to sanity-check each tool
if __name__ == "__main__":
    import json

    print("=== search_knowledge_base (no API key needed) ===")
    print(json.dumps(search_knowledge_base("How do I reset my password?"), indent=2))
    if os.environ.get("GEMINI_API_KEY"):
        print("\n=== classify_request ===")
        print(json.dumps(classify_request("I cannot login after resetting my password."), indent=2))
        print("\n=== create_task_object ===")
        print(
            json.dumps(
                create_task_object(
                    "Create a follow-up task for the finance team because the customer has not received the invoice."
                ),
                indent=2,
            )
        )
    else:
        print("\n(Skipping classify_request / create_task_object - set GEMINI_API_KEY to test these.)")