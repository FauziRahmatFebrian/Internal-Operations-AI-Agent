"""
run_evaluation.py - Runs the agent against data/sample_requests.csv and
writes a filled-in evaluation.md with REAL results (Task 6).

This script does not simulate or guess results - it actually calls
run_agent() for every row, so the numbers in evaluation.md always match
what the agent really produced. Requires GEMINI_API_KEY to be set.

QUOTA-FRIENDLY BY DESIGN: progress is checkpointed to eval_progress.json
after every row. If you hit a 429 (rate limit) partway through, just wait
for your quota to reset and run this script again - it will skip rows
that already succeeded and only call the API for the remaining ones,
instead of burning quota re-running everything from scratch.

Usage:
    python run_evaluation.py
    python run_evaluation.py --limit 8   # only process the first 8 rows
                                          # (8 is the brief's minimum)
"""
import argparse
import json
import os
import sys

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent  # noqa: E402
from google.genai.errors import ClientError  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_requests.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "evaluation.md")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "eval_progress.json")

# Heuristic expected tool set per LABELED expected_intent (not per the
# agent's actual runtime intent, which can legitimately differ - e.g. a
# knowledge_question that gets reclassified to cannot_answer because no KB
# doc cleared the threshold). This is why tool selection accuracy is a
# heuristic, not ground truth - see the note printed with the metric.
EXPECTED_TOOLS_BY_INTENT = {
    "knowledge_question": {"classify_request", "search_knowledge_base"},
    "ticket_triage": {"classify_request", "search_knowledge_base"},
    "create_task": {"classify_request", "create_task_object"},
    "summarize_request": {"classify_request", "search_knowledge_base", "summarize_text"},
    "cannot_answer": {"classify_request"},
}


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(checkpoint: dict) -> None:
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N rows.")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY before running run_evaluation.py.")

    df = pd.read_csv(DATA_PATH)
    if args.limit:
        df = df.head(args.limit)

    checkpoint = load_checkpoint()
    already_done = set(checkpoint.keys())
    remaining = [rid for rid in df["request_id"] if rid not in already_done]

    print(f"{len(already_done & set(df['request_id']))} of {len(df)} rows already "
          f"completed from a previous run. {len(remaining)} left to process.")

    for _, row in df.iterrows():
        request_id = row["request_id"]
        if request_id in checkpoint:
            continue  # already have a real result from a previous run

        try:
            output = run_agent(row["user_input"])
        except ClientError as e:
            if getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e):
                print(f"\nHit a rate/quota limit at {request_id}. "
                      f"Progress saved - {len(checkpoint)}/{len(df)} rows done so far.")
                print("Wait for your quota to reset, then run this script again "
                      "to continue from here.")
                save_checkpoint(checkpoint)
                sys.exit(0)
            raise  # a different API error - don't swallow it silently

        checkpoint[request_id] = {
            "user_input": row["user_input"],
            "expected_intent": row["expected_intent"],
            "predicted_intent": output["intent"],
            "tools_used": output["tools_used"],
            "confidence": output["confidence"],
            "recommended_action": output["recommended_action"],
        }
        save_checkpoint(checkpoint)  # persist after every single row
        print(f"  {request_id}: done ({output['intent']})")

    if len(checkpoint) < len(df):
        print(f"\nOnly {len(checkpoint)}/{len(df)} rows completed - run this script "
              f"again to finish before generating evaluation.md.")
        return

    _write_evaluation_md(df, checkpoint)


def _write_evaluation_md(df: pd.DataFrame, checkpoint: dict) -> None:
    rows = []
    correct_intent = 0
    correct_tools = 0

    for _, row in df.iterrows():
        c = checkpoint[row["request_id"]]
        is_correct = c["predicted_intent"] == row["expected_intent"]
        correct_intent += int(is_correct)

        expected_tool_set = EXPECTED_TOOLS_BY_INTENT.get(row["expected_intent"], set())
        tools_correct = set(c["tools_used"]) == expected_tool_set
        correct_tools += int(tools_correct)

        rows.append({
            "no": row["request_id"],
            "user_input": row["user_input"],
            "expected_intent": row["expected_intent"],
            "predicted_intent": c["predicted_intent"],
            "correct": "Yes" if is_correct else "No",
            "tools_used": ", ".join(c["tools_used"]),
            "tools_correct": "Yes" if tools_correct else "No",
        })

    n = len(rows)
    intent_accuracy = correct_intent / n if n else 0
    tool_accuracy = correct_tools / n if n else 0

    lines = []
    lines.append("# Evaluation\n")
    lines.append(f"Total test cases: {n}\n")
    lines.append("## Results Table\n")
    lines.append(
        "| No | User Input | Expected Intent | Predicted Intent | Correct? | Tools Used | Tools Correct? |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['no']} | {r['user_input']} | {r['expected_intent']} | "
            f"{r['predicted_intent']} | {r['correct']} | {r['tools_used']} | {r['tools_correct']} |"
        )

    lines.append("\n## Metrics\n")
    lines.append(f"- Intent accuracy: {correct_intent}/{n} = {intent_accuracy:.1%}")
    lines.append(f"- Tool selection accuracy: {correct_tools}/{n} = {tool_accuracy:.1%}")
    lines.append(
        "  - _Heuristic, not ground truth_: compares `tools_used` against a fixed "
        "expected set per labeled `expected_intent`. A row can legitimately score "
        "'No' even when the agent behaved correctly (e.g. correctly reclassified "
        "to `cannot_answer`). Review 'No' rows by hand."
    )

    lines.append("\n## Analysis\n")
    lines.append("1. **Case mana yang berhasil?** _(fill in after reviewing the table above)_")
    lines.append("2. **Case mana yang gagal?** _(fill in)_")
    lines.append("3. **Mengapa agent gagal?** _(fill in)_")
    lines.append("4. **Bagaimana cara memperbaiki agent?** _(fill in)_")
    lines.append("5. **Apa risiko hallucination dari agent ini?** _(fill in - reference the verbatim-KB-content design in agent.py)_")
    lines.append("6. **Bagaimana agent menangani informasi yang tidak tersedia?** _(fill in - reference KB_SCORE_THRESHOLD)_")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nWrote {OUTPUT_PATH} - intent accuracy {correct_intent}/{n} = {intent_accuracy:.1%}, "
          f"tool accuracy {correct_tools}/{n} = {tool_accuracy:.1%}")
    print("Now open evaluation.md and fill in the Analysis section by hand.")


if __name__ == "__main__":
    main()