# streamlit_app.py
import streamlit as st
import requests
import pandas as pd
import html
import time
from datetime import datetime, timezone
import io
import matplotlib.pyplot as plt

# ---------- Configuration ----------
API_BASE = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{API_BASE}/chat"
LOGS_ENDPOINT = f"{API_BASE}/logs"
ANALYSIS_ENDPOINT = f"{API_BASE}/analysis"


# ---------- Helpers ----------
def send_message_to_api(
    message: str, user_id: str | None = None, conversation_id: str | None = None
):
    payload = {"message": message}
    if user_id:
        payload["user_id"] = user_id
    if conversation_id:
        payload["conversation_id"] = conversation_id
    resp = requests.post(CHAT_ENDPOINT, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()  # { reply, category, log_id }


def fetch_logs(limit: int = 200):
    resp = requests.get(f"{LOGS_ENDPOINT}?limit={limit}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_analysis():
    resp = requests.get(ANALYSIS_ENDPOINT, timeout=30)
    resp.raise_for_status()
    return resp.json()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- Streamlit UI ----------
st.set_page_config(
    page_title="Chatbot UI", layout="wide", initial_sidebar_state="expanded"
)

# Initialize session state
if "history" not in st.session_state:
    st.session_state["history"] = []
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""

# Sidebar
with st.sidebar:
    st.title("FastAPI Chatbot")
    st.markdown("A lightweight Streamlit UI for your FastAPI chatbot.")
    st.divider()
    user_id = st.text_input(
        "User ID (optional)", value=st.session_state.get("user_id", "hari")
    )
    st.session_state["user_id"] = user_id

    if st.button("Reset conversation"):
        st.session_state.pop("conversation_id", None)
        st.session_state["history"] = []
        st.rerun()

    st.divider()
    st.markdown("#### Analysis")
    if st.button("Refresh analysis"):
        try:
            st.session_state["analysis"] = fetch_analysis()
        except Exception as e:
            st.error(f"Failed to refresh analysis: {e}")

    if "analysis" not in st.session_state:
        try:
            st.session_state["analysis"] = fetch_analysis()
        except Exception:
            st.session_state["analysis"] = {"counts": {}, "most_used": None}

    counts = st.session_state["analysis"].get("counts", {})
    most_used = st.session_state["analysis"].get("most_used", None)
    st.write("Most used:", f"**{most_used}**" if most_used else "â€”")

    # Bar chart using matplotlib
    if counts:
        labels = list(counts.keys())
        values = [counts[k] for k in labels]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(labels, values)
        ax.set_ylabel("Count")
        ax.set_title("Messages by Category")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

    st.divider()
    st.markdown("Developer")
    st.markdown("- Backend: FastAPI\n- DB: SQLite\n- Vector DB: Chroma\n- LLM: OpenAI")
    st.caption("Change API base: set streamlit secret `api_base`")

# Main layout: chat left, logs + tools right
col1, col2 = st.columns([3, 2])

# Chat column
with col1:
    st.header("Chat")

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state["history"]):
            ts = msg.get("time", "")
            role = msg["role"]
            category = msg.get("category", "")

            if role == "user":
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:flex-end;margin:8px 0">
                      <div style="max-width:75%;background:#2d5aa0;padding:12px;border-radius:12px;border:1px solid #4a6fa5;">
                        <div style="font-size:14px;white-space:pre-wrap;color:#ffffff;">{html.escape(msg["text"])}</div>
                        <div style="font-size:11px;color:#b8c5d1;margin-top:6px;text-align:right">{ts}{f" â€¢ {category}" if category else ""}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:  # bot
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:flex-start;margin:8px 0">
                      <div style="max-width:75%;background:#3a3a3a;padding:12px;border-radius:12px;border:1px solid #555555;">
                        <div style="font-size:14px;white-space:pre-wrap;color:#ffffff;">{html.escape(msg["text"])}</div>
                        <div style="font-size:11px;color:#b0b0b0;margin-top:6px">{ts}{f" â€¢ {category}" if category else ""}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Input area - using chat_input instead of form for better UX
    user_input = st.chat_input("Type your message here...")

    # Process user input (from either chat_input or form)
    if user_input and user_input.strip():
        # Add user message to history
        message_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        st.session_state["history"].append(
            {"role": "user", "text": user_input.strip(), "time": message_time}
        )

        # Get conversation settings
        conv_id = st.session_state.get("conversation_id")
        current_user_id = st.session_state.get("user_id", "")
        persist_conversation = globals().get("persist_conversation", True)

        # Show spinner and get bot response
        with st.spinner("Bot is thinking..."):
            try:
                resp = send_message_to_api(
                    message=user_input.strip(),
                    user_id=current_user_id if current_user_id else None,
                    conversation_id=conv_id if persist_conversation else None,
                )

                bot_reply = resp.get("reply", "No response from API")
                category = resp.get("category", "other")
                log_id = resp.get("log_id")

                # Update conversation_id if needed
                if persist_conversation and "conversation_id" not in st.session_state:
                    st.session_state["conversation_id"] = str(int(time.time()))

                # Add bot response to history
                reply_time = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
                st.session_state["history"].append(
                    {
                        "role": "bot",
                        "text": bot_reply,
                        "time": reply_time,
                        "category": category,
                        "log_id": log_id,
                    }
                )

                # Force rerun to show the new messages
                st.rerun()

            except requests.HTTPError as e:
                error_msg = f"API error: {e}"
                if hasattr(e, "response") and e.response is not None:
                    try:
                        error_detail = e.response.json()
                        error_msg += f" - {error_detail}"
                    except:
                        error_msg += f" - {e.response.text}"
                st.error(error_msg)

            except Exception as e:
                st.error(f"Failed to call API: {e}")

    # Clear chat button
    if st.button("Clear chat UI", key="clear_chat"):
        st.session_state["history"] = []
        st.rerun()

# Right column: logs and tools
with col2:
    st.header("Logs & Tools")

    # Add debug info
    with st.expander("Debug Info", expanded=False):
        st.write("History length:", len(st.session_state.get("history", [])))
        st.write("Conversation ID:", st.session_state.get("conversation_id", "None"))
        st.write("User ID:", st.session_state.get("user_id", "None"))

    st.subheader("Recent logs")
    try:
        logs = fetch_logs(limit=50)

        if logs:
            # Convert to DataFrame
            df = pd.DataFrame(logs)
            # Show limited columns
            display_columns = [
                "id",
                "conversation_id",
                "user_id",
                "user_message",
                "bot_response",
                "category",
                "created_at",
            ]
            # Only show columns that exist
            available_columns = [col for col in display_columns if col in df.columns]
            show_df = df[available_columns].copy()

            if "created_at" in show_df.columns:
                show_df["created_at"] = pd.to_datetime(show_df["created_at"])

            st.dataframe(show_df, width="stretch")

            # Download CSV
            csv_buf = io.StringIO()
            show_df.to_csv(csv_buf, index=False)
            st.download_button(
                "Download logs CSV",
                data=csv_buf.getvalue(),
                file_name=f"chat_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        else:
            st.write("No logs yet.")

    except Exception as e:
        st.error(f"Failed to fetch logs: {e}")

    st.divider()
    st.subheader("Quick actions")
    if st.button("Refresh logs", key="refresh_logs"):
        st.rerun()

    st.write("API base:", API_BASE)
    st.write("Docs:", f"{API_BASE}/docs")

# Footer
st.markdown("---")
st.caption(
    "Streamlit UI for FastAPI chatbot â€” built for quick prototyping. "
    "Customize styles or add authentication as needed."
)
