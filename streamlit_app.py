import os
import streamlit as st
from dotenv import load_dotenv
load_dotenv()
from agent import run_agent
st.set_page_config(
    page_title="Internal Operations AI Agent",
    page_icon="🛠️",
    layout="wide",
)

st.markdown("""
<style>

/* Hilangkan batas maksimal bawaan Streamlit */
.block-container{
    max-width:100%;
    padding-top:2rem;
    padding-left:3rem;
    padding-right:3rem;
    padding-bottom:1rem;
}

/* Semua container memenuhi lebar */
[data-testid="stVerticalBlock"]{
    width:100%;
}

/* Border container mengikuti parent */
[data-testid="stVerticalBlockBorderWrapper"]{
    width:100%;
}

/* Chat input */
[data-testid="stChatInput"]{
    width:100%;
}

/* Sedikit memperbesar area chat */
[data-testid="stChatMessageContent"]{
    font-size:16px;
}

</style>
""", unsafe_allow_html=True)

if not os.environ.get("GEMINI_API_KEY"):
    st.error("GEMINI_API_KEY belum di-set. Isi file .env lalu restart aplikasi ini.")
    st.stop()


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "display": (
                "Halo! Saya AI agent operasional internal.\n\n"
                "Tanyakan sesuatu, laporkan masalah, atau minta saya membuat task."
            ),
            "raw": None,
        }
    ]


def _display_text(output: dict) -> str:

    intent = output["intent"]
    result = output["result"]

    if intent == "create_task":
        task = result["task"]

        return (
            f"### ✅ Task dibuat\n\n"
            f"**Judul** : {task['title']}\n\n"
            f"**Tim** : {task['assigned_team']}\n\n"
            f"**Prioritas** : {task['priority']}\n\n"
            f"**Deskripsi** :\n{task['description']}"
        )

    if intent == "ticket_triage":

        text = (
            f"### 🎫 Hasil Analisis\n\n"
            f"**Kategori** : {result.get('category')}\n\n"
            f"**Prioritas** : {result.get('priority')}"
        )

        if result.get("answer"):
            text += f"\n\n{result['answer']}"

        return text

    return result.get("answer", "(tidak ada jawaban)")


with st.container(border=True):

    col1, col2 = st.columns([1, 15])

    with col1:
        st.markdown(
            "<div style='font-size:35px;text-align:center;'>🛠️</div>",
            unsafe_allow_html=True,
        )

    with col2:

        st.markdown("## Internal Operations AI Agent")

        st.caption(
            "Tanya kebijakan internal • Laporkan masalah • "
            "Buat task • Ringkas dokumen"
        )

user_input = st.chat_input("Ketik pertanyaan...")

if user_input:

    st.session_state.messages.append(
        {
            "role": "user",
            "display": user_input,
            "raw": None,
        }
    )

    with st.spinner("Memproses..."):

        try:

            output = run_agent(user_input)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "display": _display_text(output),
                    "raw": output,
                }
            )

        except Exception as e:

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "display": f"Terjadi error:\n\n{e}",
                    "raw": None,
                }
            )

with st.container(height=650, border=True):

    for msg in st.session_state.messages:

        with st.chat_message(msg["role"]):

            st.markdown(msg["display"])

            if msg["raw"] is not None:

                with st.expander("Lihat JSON mentah"):

                    st.json(msg["raw"])