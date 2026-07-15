"""
main.py - Simple CLI interface for the Internal Operations AI Agent.

Usage:
    python main.py
    > How do I reset my password?
"""
import json

from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables (GEMINI_API_KEY etc.)

from agent import run_agent  # noqa: E402  (import after load_dotenv on purpose)


def main():
    print("Internal Operations AI Agent (type 'exit' to quit)")
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        try:
            output = run_agent(user_input)
        except Exception as e:  # keep the CLI alive on a single bad turn
            print(json.dumps({"error": str(e)}, indent=2))
            continue

        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
