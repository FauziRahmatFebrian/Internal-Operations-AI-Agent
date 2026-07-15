"""
streamlit_app.py - Optional web chat interface for the Internal Operations
AI Agent. Task 5 alternative to the CLI in main.py - the brief allows
CLI, Streamlit, Gradio, or FastAPI; CLI alone is enough for 2 days, this
is extra polish on top of it.

Run with:
    streamlit run streamlit_app.py
"""
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent  # noqa: E402

st.set_page_config(page_title="Internal Operations AI Agent", page_icon="\U0001F6E0\uFE0F")

if not os.environ.get("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY belum di-set. Isi file .env lalu restart aplikasi ini.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "display": (
                "Halo! Saya AI agent operasional internal. Tanyakan sesuatu, "
                "laporkan masalah, atau minta saya buatkan task."
            ),
            "raw": None,
        }
    ]


def _display_text(output: dict) -> str:
    """Pulls a short human-readable summary out of run_agent()'s JSON output.

    The raw JSON is still always shown too (in an expander) - this is only
    a friendlier rendering on top of it, not a replacement for it.
    """
    intent = output["intent"]
    result = output["result"]

    if intent == "create_task":
        task = result["task"]
        return (
            f"**Task dibuat (simulasi):** {task['title']}\n\n"
            f"- Tim: {task['assigned_team']}\n"
            f"- Prioritas: {task['priority']}\n"
            f"- Deskripsi: {task['description']}"
        )

    if intent == "ticket_triage":
        text = f"**Kategori:** {result.get('category')} | **Prioritas:** {result.get('priority')}"
        if result.get("answer"):
            text += f"\n\n{result['answer']}"
        return text

    # knowledge_question, summarize_request, cannot_answer all use "answer"
    return result.get("answer", "(tidak ada jawaban)")


# --- Header box -------------------------------------------------------
with st.container(border=True):
    icon_col, title_col = st.columns([1, 10])
    with icon_col:
        st.markdown(
            "<div style='font-size:28px; text-align:center;'>\U0001F6E0\uFE0F</div>",
            unsafe_allow_html=True,
        )
    with title_col:
        st.markdown("**Internal Operations AI Agent**")
        st.caption(
            "Tanya soal kebijakan internal, laporkan masalah, minta dibuatkan "
            "task, atau minta ringkasan kebijakan."
        )

# --- Handle new input BEFORE rendering, so it's included in this run's
#     render pass inside the boxed chat area below ----------------------
user_input = st.chat_input("Tanya sesuatu ke agent...")

if user_input:
    st.session_state.messages.append({"role": "user", "display": user_input, "raw": None})
    with st.spinner("Memproses..."):
        try:
            output = run_agent(user_input)
            display_text = _display_text(output)
            st.session_state.messages.append(
                {"role": "assistant", "display": display_text, "raw": output}
            )
        except Exception as e:
            error_text = f"Terjadi error: {e}"
            st.session_state.messages.append(
                {"role": "assistant", "display": error_text, "raw": None}
            )

# --- Chat box: bordered, fixed-height, internally scrollable -----------
with st.container(height=480, border=True):
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["display"])
            if msg["raw"] is not None:
                with st.expander("Lihat JSON mentah"):
                    st.json(msg["raw"])