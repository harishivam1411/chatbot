# streamlit_app.py (Enhanced Version)
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
CONTEXT_ENDPOINT = f"{API_BASE}/chat/context"


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
    return resp.json()  # { reply, category, log_id, conversation_id, context_offered }


def fetch_logs(limit: int = 200):
    resp = requests.get(f"{LOGS_ENDPOINT}?limit={limit}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_analysis():
    resp = requests.get(ANALYSIS_ENDPOINT, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_user_context(user_id: str):
    """Fetch conversation context for a user"""
    try:
        resp = requests.get(f"{CONTEXT_ENDPOINT}/{user_id}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- Streamlit UI ----------
st.set_page_config(
    page_title="Enhanced Chatbot UI", layout="wide", initial_sidebar_state="expanded"
)

# Add custom CSS for enhanced UI
st.markdown(
    """
<style>
/* Enhanced chat container styling */
.chat-container {
    height: 60vh;
    overflow-y: auto;
    padding: 10px;
    border: 1px solid #333;
    border-radius: 10px;
    background-color: #1e1e1e;
    margin-bottom: 80px;
}

/* Continuation offer styling */
.continuation-message {
    background: linear-gradient(135deg, #2d5aa0, #4a6fa5) !important;
    border: 2px solid #5a7fb8 !important;
    box-shadow: 0 2px 8px rgba(45, 90, 160, 0.3) !important;
}

/* Context indicator */
.context-indicator {
    background: #2d4a22;
    color: #90c879;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 11px;
    margin-left: 8px;
    display: inline-block;
}

/* User response to continuation */
.continuation-response {
    border: 2px solid #4a6fa5 !important;
}

/* Enhanced message styling */
.user-message, .bot-message {
    margin: 8px 0;
    animation: fadeIn 0.3s ease-in;
    transition: all 0.2s ease;
}

.user-message:hover, .bot-message:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Enhanced input styling */
.fixed-input-container {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    width: 45%;
    z-index: 1000;
    background: #0e1117;
    padding: 10px;
    border-radius: 10px;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.3);
}

.fixed-input-container input {
    width: 100%;
    padding: 15px;
    border: 2px solid #333;
    border-radius: 25px;
    background: #262730;
    color: white;
    font-size: 16px;
    outline: none;
}

.fixed-input-container input:focus {
    border-color: #2d5aa0;
}

/* Context panel styling */
.context-panel {
    background: #1e1e1e;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
}

.context-summary {
    color: #90c879;
    font-style: italic;
    font-size: 14px;
}
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "history" not in st.session_state:
    st.session_state["history"] = []
if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""
if "last_context_check" not in st.session_state:
    st.session_state["last_context_check"] = None
if "user_context" not in st.session_state:
    st.session_state["user_context"] = None

# Sidebar
with st.sidebar:
    st.title("🤖 Enhanced Chatbot")
    st.markdown("A context-aware chatbot with conversation continuity.")
    st.divider()
    
    # User settings
    user_id = st.text_input(
        "User ID (required for context)", 
        value=st.session_state.get("user_id", "hari"),
        help="Enter a user ID to enable conversation continuity"
    )
    st.session_state["user_id"] = user_id

    # Fetch user context if user_id is provided and different from last check
    if user_id and user_id != st.session_state.get("last_context_check"):
        with st.spinner("Checking conversation history..."):
            context_data = fetch_user_context(user_id)
            st.session_state["user_context"] = context_data
            st.session_state["last_context_check"] = user_id

    # Display user context if available
    if st.session_state.get("user_context"):
        context = st.session_state["user_context"]
        st.markdown("#### 📋 Conversation Context")
        
        if context.get("should_offer_continuation"):
            st.success("🔄 Previous conversation detected!")
            context_info = context.get("context", {})
            if context_info:
                st.markdown(f"**Topic:** {context_info.get('conversation_summary', 'N/A')}")
                st.markdown(f"**Category:** {context_info.get('dominant_category', 'N/A')}")
                if context_info.get('last_activity'):
                    st.markdown(f"**Last active:** {context_info['last_activity']}")
        else:
            st.info("✨ Starting fresh conversation")

    st.divider()
    
    # Conversation settings
    st.markdown("#### ⚙️ Settings")
    
    persist_conversation = st.checkbox(
        "Enable conversation continuity", 
        value=True,
        help="Maintain conversation context across sessions"
    )
    
    show_categories = st.checkbox(
        "Show message categories", 
        value=True,
        help="Display message categories in chat"
    )
    
    st.divider()
    st.markdown("#### 📊 Analysis")

    if "analysis" not in st.session_state:
        try:
            st.session_state["analysis"] = fetch_analysis()
        except Exception:
            st.session_state["analysis"] = {"counts": {}, "most_used": None}

    counts = st.session_state["analysis"].get("counts", {})
    most_used = st.session_state["analysis"].get("most_used", None)
    st.write("Most used:", f"**{most_used}**" if most_used else "—")

    # Enhanced bar chart with conversation continuity metrics
    if counts:
        labels = list(counts.keys())
        values = [counts[k] for k in labels]
        
        # Create enhanced chart
        fig, ax = plt.subplots(figsize=(6, 4))
        colors = ['#2d5aa0', '#4a6fa5', '#90c879', '#c87979', '#c879b4', '#79c8c8']
        bars = ax.bar(labels, values, color=colors[:len(labels)])
        
        ax.set_ylabel("Count")
        ax.set_title("Messages by Category")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Highlight continuation-related categories
        for i, (label, bar) in enumerate(zip(labels, bars)):
            if 'continuation' in label.lower():
                bar.set_color('#ff6b6b')
                bar.set_alpha(0.8)
        
        st.pyplot(fig)
        plt.close()

    st.divider()
    st.markdown("#### ℹ️ About")
    st.markdown("""
    **Enhanced Features:**
    - 🔄 Conversation continuity
    - 🧠 Context-aware responses  
    - 📚 Learning session tracking
    - 🎯 Smart topic detection
    """)
    
    st.markdown("**Tech Stack:**")
    st.markdown("- Backend: FastAPI\n- DB: SQLite\n- Vector DB: Chroma\n- LLM: OpenAI\n- Context: Custom service")

# Main layout: chat left, logs + tools right
col1, col2 = st.columns([3, 2])

# Chat column
with col1:
    st.header("💬 Smart Chat")

    # Display conversation context summary if available
    if (st.session_state.get("user_context") and 
        st.session_state["user_context"].get("should_offer_continuation")):
        context_info = st.session_state["user_context"].get("context", {})
        with st.expander("🧠 Previous Conversation Context", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Messages", context_info.get("message_count", 0))
                st.write(f"**Category:** {context_info.get('dominant_category', 'N/A')}")
            with col_b:
                if context_info.get('last_activity'):
                    st.write(f"**Last active:** {context_info['last_activity']}")
            st.write(f"**Topic:** {context_info.get('conversation_summary', 'N/A')}")

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state["history"]):
            ts = msg.get("time", "")
            role = msg["role"]
            category = msg.get("category", "")
            log_id = msg.get("log_id", "")

            # Determine if this is a special message type
            is_continuation_offer = category == "continuation_offer"
            is_continuation_response = category == "continuation_response"
            
            if role == "user":
                # Enhanced user message styling
                extra_class = "continuation-response" if is_continuation_response else ""
                category_display = f" • {category}" if show_categories and category else ""
                
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:flex-end;margin:8px 0">
                      <div class="user-message {extra_class}" style="max-width:75%;background:#2d5aa0;padding:12px;border-radius:12px;border:1px solid #4a6fa5;">
                        <div style="font-size:14px;white-space:pre-wrap;color:#ffffff;">{html.escape(msg["text"])}</div>
                        <div style="font-size:11px;color:#b8c5d1;margin-top:6px;text-align:right">
                          {ts}{category_display}
                          {f'<span class="context-indicator">ID: {log_id}</span>' if log_id else ''}
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:  # bot
                # Enhanced bot message styling
                extra_class = "continuation-message" if is_continuation_offer else ""
                category_display = f" • {category}" if show_categories and category else ""
                
                # Special icon for continuation offers
                icon = "🔄" if is_continuation_offer else "🤖"
                
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:flex-start;margin:8px 0">
                      <div class="bot-message {extra_class}" style="max-width:75%;background:#3a3a3a;padding:12px;border-radius:12px;border:1px solid #555555;">
                        <div style="font-size:14px;white-space:pre-wrap;color:#ffffff;">
                          <span style="margin-right:8px;">{icon}</span>{html.escape(msg["text"])}
                        </div>
                        <div style="font-size:11px;color:#b0b0b0;margin-top:6px">
                          {ts}{category_display}
                          {f'<span class="context-indicator">ID: {log_id}</span>' if log_id else ''}
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Enhanced input form
    with st.form(key="chat_form", clear_on_submit=True):
        # Create columns for input and button
        input_col, button_col = st.columns([5, 1])
        with input_col:
            user_input = st.text_input(
                "Message",
                key="message_input",
                placeholder="Type your message here... (context-aware responses enabled)" if user_id else "Enter User ID in sidebar for enhanced features",
                label_visibility="collapsed",
            )
        with button_col:
            submitted = st.form_submit_button("Send", use_container_width=True)

        # Process form submission
        if submitted and user_input and user_input.strip():
            # Add user message to history
            message_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Determine category for user message (for display purposes)
            from app.services.classifier import classify_message, is_likely_continuation_response
            user_category = classify_message(user_input.strip())
            if is_likely_continuation_response(user_input.strip()):
                user_category = "continuation_response"
            
            st.session_state["history"].append(
                {
                    "role": "user", 
                    "text": user_input.strip(), 
                    "time": message_time,
                    "category": user_category
                }
            )

            # Get conversation settings
            conv_id = st.session_state.get("conversation_id")
            current_user_id = st.session_state.get("user_id", "")

            # Show enhanced spinner with context info
            spinner_text = "🧠 Analyzing context and generating response..." if current_user_id else "🤖 Generating response..."
            
            with st.spinner(spinner_text):
                try:
                    resp = send_message_to_api(
                        message=user_input.strip(),
                        user_id=current_user_id if current_user_id else None,
                        conversation_id=conv_id if persist_conversation else None,
                    )

                    bot_reply = resp.get("reply", "No response from API")
                    category = resp.get("category", "other")
                    log_id = resp.get("log_id")
                    returned_conv_id = resp.get("conversation_id")
                    context_offered = resp.get("context_offered", False)

                    # Update conversation_id if we got one back
                    if returned_conv_id and persist_conversation:
                        st.session_state["conversation_id"] = returned_conv_id

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

                    # If this was a continuation offer, update UI state
                    if category == "continuation_offer":
                        st.info("💡 The bot has offered to continue your previous conversation!")

                    # Force rerun to show the new messages
                    st.rerun()

                except requests.HTTPError as e:
                    error_msg = f"❌ API error: {e}"
                    if hasattr(e, "response") and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            error_msg += f" - {error_detail}"
                        except:
                            error_msg += f" - {e.response.text}"
                    st.error(error_msg)

                except Exception as e:
                    st.error(f"❌ Failed to call API: {e}")

# Right column: enhanced logs and tools
with col2:
    st.header("📋 Activity Monitor")
    
    # Enhanced logs display
    try:
        logs = fetch_logs(limit=50)

        if logs:
            # Convert to DataFrame with enhanced processing
            df = pd.DataFrame(logs)
            
            # Add derived columns for better analysis
            if "category" in df.columns:
                df["is_continuation"] = df["category"].str.contains("continuation", na=False)
                df["is_learning"] = df["category"].str.contains("learn", na=False)
            
            # Show enhanced metrics
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                total_messages = len(df)
                st.metric("Total Messages", total_messages)
            with col_m2:
                continuation_count = df["is_continuation"].sum() if "is_continuation" in df.columns else 0
                st.metric("Continuations", continuation_count)
            with col_m3:
                unique_users = df["user_id"].nunique() if "user_id" in df.columns else 0
                st.metric("Unique Users", unique_users)
            
            # Enhanced data display
            display_columns = [
                "id", "conversation_id", "user_id", "user_message", 
                "bot_response", "category", "created_at"
            ]
            available_columns = [col for col in display_columns if col in df.columns]
            show_df = df[available_columns].copy()

            if "created_at" in show_df.columns:
                show_df["created_at"] = pd.to_datetime(show_df["created_at"])

            # Color-code continuation messages
            def highlight_continuations(row):
                if "continuation" in str(row.get("category", "")).lower():
                    return ['background-color: #2d4a22'] * len(row)
                return [''] * len(row)

            if "category" in show_df.columns:
                styled_df = show_df.style.apply(highlight_continuations, axis=1)
                st.dataframe(styled_df, width="stretch", height=300)
            else:
                st.dataframe(show_df, width="stretch", height=300)

            # Enhanced CSV download
            csv_buf = io.StringIO()
            show_df.to_csv(csv_buf, index=False)
            st.download_button(
                "📥 Download Enhanced Logs",
                data=csv_buf.getvalue(),
                file_name=f"enhanced_chat_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        else:
            st.info("No conversation logs yet. Start chatting to see activity!")

    except Exception as e:
        st.error(f"❌ Failed to fetch logs: {e}")

    st.subheader("🛠️ Quick Actions")
    
    # Enhanced action buttons in 2x2 grid
    button1, button2 = st.columns(2) 
    button3, button4 = st.columns(2)

    with button1:
        if st.button("🔄 Refresh logs", key="refresh_logs"):
            st.rerun()

    with button2:
        if st.button("🧹 Clear chat", key="clear_chat"):
            st.session_state["history"] = []
            st.rerun()

    with button3:
        if st.button("📊 Refresh analysis"):
            try:
                st.session_state["analysis"] = fetch_analysis()
                st.success("Analysis refreshed!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to refresh: {e}")

    with button4:
        if st.button("🆕 New conversation", key="reset_conversation"):
            st.session_state.pop("conversation_id", None)
            st.session_state["history"] = []
            # Refresh context for the user
            if st.session_state.get("user_id"):
                context_data = fetch_user_context(st.session_state["user_id"])
                st.session_state["user_context"] = context_data
            st.rerun()

    # Context management section
    st.subheader("🧠 Context Controls")
    
    if st.session_state.get("user_id"):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🔍 Check Context", key="check_context"):
                with st.spinner("Checking conversation context..."):
                    context_data = fetch_user_context(st.session_state["user_id"])
                    st.session_state["user_context"] = context_data
                    st.rerun()
        
        with col_c2:
            if st.button("🗑️ Clear Context", key="clear_context"):
                st.session_state["user_context"] = None
                st.session_state["last_context_check"] = None
                st.success("Context cleared!")
    else:
        st.info("Enter a User ID to enable context features")

    # Debug information (expandable)
    with st.expander("🔧 Debug Info", expanded=False):
        st.json({
            "conversation_id": st.session_state.get("conversation_id"),
            "user_id": st.session_state.get("user_id"),
            "message_count": len(st.session_state.get("history", [])),
            "context_available": bool(st.session_state.get("user_context")),
            "should_offer_continuation": st.session_state.get("user_context", {}).get("should_offer_continuation", False)
        })