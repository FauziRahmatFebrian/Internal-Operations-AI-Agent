from tools import (
    search_knowledge_base,
    classify_request,
    create_task_object,
    summarize_text,
    validate_json_output,
)

KB_SCORE_THRESHOLD = 0.15
def _answer_from_kb(kb_result: dict) -> dict:
    """Builds a grounded answer strictly from the retrieved KB doc content."""
    top = kb_result["results"][0]
    return {
        "answer": top["content"],
        "sources": [{"doc_id": top["doc_id"], "title": top["title"]}],
    }
def _no_answer() -> dict:
    return {
        "answer": "I cannot answer this question based on the available knowledge base.",
        "sources": [],
    }


def run_agent(user_input: str) -> dict:
    tools_used = []
    classification = classify_request(user_input)
    tools_used.append("classify_request")
    intent = classification["intent"]
    if intent == "knowledge_question":
        kb_result = search_knowledge_base(user_input)
        tools_used.append("search_knowledge_base")

        if kb_result["results"] and kb_result["results"][0]["score"] >= KB_SCORE_THRESHOLD:
            result = _answer_from_kb(kb_result)
            confidence = classification["confidence"]
            recommended_action = "Answer user directly"
        else:
            result = _no_answer()
            confidence = "low"
            recommended_action = "Escalate to human support"
            intent = "cannot_answer"

    elif intent == "summarize_request":
        kb_result = search_knowledge_base(user_input, top_k=5)
        tools_used.append("search_knowledge_base")
        qualifying_docs = [
            r for r in kb_result["results"] if r["score"] >= KB_SCORE_THRESHOLD
        ]

        if qualifying_docs:
            summary_result = summarize_text(user_input, qualifying_docs)
            tools_used.append(summary_result["tool_name"])
            result = {
                "answer": summary_result["summary"],
                "sources": summary_result["sources"],
            }
            confidence = classification["confidence"]
            recommended_action = "Answer user directly"
        else:
            result = _no_answer()
            confidence = "low"
            recommended_action = "Escalate to human support"
            intent = "cannot_answer"

    elif intent == "ticket_triage":
        kb_result = search_knowledge_base(user_input)
        tools_used.append("search_knowledge_base")

        result = {
            "category": classification["category"],
            "priority": classification["priority"],
        }
        if kb_result["results"] and kb_result["results"][0]["score"] >= KB_SCORE_THRESHOLD:
            result.update(_answer_from_kb(kb_result))
            recommended_action = (
                f"Escalate to {classification['category']} team if the user's issue persists"
            )
        else:
            result["answer"] = None
            result["sources"] = []
            recommended_action = f"Escalate to {classification['category']} team"

        confidence = classification["confidence"]

    elif intent == "create_task":
        task_result = create_task_object(
            user_input,
            assigned_team=classification["category"],
            priority=classification["priority"],
        )
        tools_used.append(task_result["tool_name"])
        result = {"task": task_result["task"], "status": task_result["status"]}
        confidence = classification["confidence"]
        recommended_action = "Review and create task in the internal system"

    else:  # cannot_answer
        result = _no_answer()
        confidence = "low"
        recommended_action = "Escalate to human support"

    output = {
        "user_input": user_input,
        "intent": intent,
        "tools_used": tools_used,
        "result": result,
        "confidence": confidence,
        "recommended_action": recommended_action,
    }
    check = validate_json_output(output)
    if not check["valid"]:
        raise ValueError(f"run_agent produced an invalid output shape: {check['errors']}")

    return output


if __name__ == "__main__":
    import json
    import os

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY before running agent.py directly.")

    for test_input in [
        "How do I reset my password?",
        "I cannot login after resetting my password.",
        "Create a follow-up task for the finance team because the customer has not received the invoice.",
        "Can I change my company tax ID?",
    ]:
        print(json.dumps(run_agent(test_input), indent=2, ensure_ascii=False))
        print("-" * 60)
