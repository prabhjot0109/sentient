import streamlit as st
import tempfile
import os
from logic.rag_engine import NPCBrain

# 1. Page Config
st.set_page_config(
    layout="wide",
    page_title="Sentinel AI",
    page_icon="🔮",
    initial_sidebar_state="expanded",
)

# 2. Modern ChatGPT-like CSS
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --bg-primary: #212121;
        --bg-secondary: #171717;
        --bg-tertiary: #2f2f2f;
        --border-color: #424242;
        --text-primary: #ececec;
        --text-secondary: #b4b4b4;
        --text-muted: #8e8e8e;
        --accent: #10a37f;
        --accent-hover: #1a7f64;
        --user-bubble: #2f2f2f;
        --assistant-bubble: transparent;
    }

    /* Hide Streamlit default elements including sidebar */
    [data-testid="stToolbar"], [data-testid="stDecoration"], header[data-testid="stHeader"] { 
        display: none !important; 
    }
    
    /* Hide default sidebar - we'll use columns instead */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Hide sidebar collapse controls */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: var(--bg-primary);
    }

    /* Left panel styling */
    .left-panel {
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border-color);
        padding: 1rem;
        height: 100vh;
        position: sticky;
        top: 0;
        overflow-y: auto;
    }

    /* Main container */
    .main .block-container {
        max-width: 100%;
        padding: 0 !important;
        margin: 0;
    }

    /* Top bar styling */
    .top-bar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        background: var(--bg-primary);
        border-bottom: 1px solid var(--border-color);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 16px;
        z-index: 1000;
    }

    .hamburger-btn {
        background: transparent;
        border: none;
        color: var(--text-primary);
        cursor: pointer;
        padding: 8px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.2s;
    }

    .hamburger-btn:hover {
        background: var(--bg-tertiary);
    }

    .logo-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .settings-btn {
        background: transparent;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        padding: 8px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }

    .settings-btn:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        padding: 1.5rem 0 !important;
        max-width: 48rem;
        margin: 0 auto;
    }

    [data-testid="stChatMessageContent"] {
        color: var(--text-primary) !important;
        font-size: 1rem;
        line-height: 1.75;
    }

    /* User message styling */
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: var(--user-bubble) !important;
        border-radius: 1.5rem !important;
        padding: 1rem 1.5rem !important;
    }

    /* Chat input container */
    .chat-input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: linear-gradient(transparent, var(--bg-primary) 50%);
        padding: 1rem 1rem 1.5rem 1rem;
    }

    .chat-input-wrapper {
        max-width: 48rem;
        margin: 0 auto;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 1.5rem;
        padding: 0.75rem 1rem;
        display: flex;
        align-items: flex-end;
        gap: 0.75rem;
    }

    [data-testid="stChatInput"] {
        padding: 0 !important;
    }

    [data-testid="stChatInput"] > div {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 1.5rem !important;
        padding: 0.75rem 1rem !important;
        max-width: 48rem;
        margin: 0 auto;
    }

    [data-testid="stChatInput"] textarea {
        color: var(--text-primary) !important;
        font-size: 1rem !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: var(--text-muted) !important;
    }

    /* Empty state */
    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 60vh;
        text-align: center;
        padding: 2rem;
    }

    .empty-state-icon {
        width: 72px;
        height: 72px;
        margin-bottom: 1.5rem;
        background: var(--bg-tertiary);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .empty-state h2 {
        color: var(--text-primary);
        font-size: 1.5rem;
        font-weight: 600;
        margin: 0 0 0.5rem 0;
    }

    .empty-state p {
        color: var(--text-secondary);
        font-size: 0.95rem;
        margin: 0;
        max-width: 400px;
    }

    /* Suggestion chips */
    .suggestions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
        margin-top: 1.5rem;
    }

    .suggestion-chip {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 1rem;
        padding: 0.625rem 1rem;
        color: var(--text-secondary);
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .suggestion-chip:hover {
        background: var(--border-color);
        color: var(--text-primary);
    }

    /* Sidebar documents list */
    .doc-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        border-radius: 0.5rem;
        cursor: pointer;
        transition: background 0.2s;
        color: var(--text-secondary);
        font-size: 0.875rem;
    }

    .doc-item:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .doc-item.active {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .doc-icon {
        width: 20px;
        height: 20px;
        opacity: 0.7;
    }

    /* Upload button */
    .upload-btn {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        border: 1px dashed var(--border-color);
        border-radius: 0.5rem;
        color: var(--text-muted);
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
        margin: 0.5rem 0.5rem;
    }

    .upload-btn:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #555; }

    /* Button overrides */
    .stButton > button {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-primary) !important;
        border-radius: 0.5rem !important;
        padding: 0.5rem 1rem !important;
        font-size: 0.875rem !important;
        transition: all 0.2s !important;
    }

    /* Ensure primary buttons (e.g., New Chat) remain clearly visible */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: var(--accent) !important;
        border-color: var(--accent) !important;
        color: var(--text-primary) !important;
    }

    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: var(--accent-hover) !important;
        border-color: var(--accent-hover) !important;
    }

    .stButton > button:hover {
        background: var(--border-color) !important;
        border-color: var(--text-muted) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: transparent !important;
    }

    [data-testid="stFileUploader"] > div {
        background: var(--bg-tertiary) !important;
        border: 1px dashed var(--border-color) !important;
        border-radius: 0.75rem !important;
    }

    [data-testid="stFileUploader"] label {
        color: var(--text-secondary) !important;
    }

    /* Text input */
    .stTextInput > div > div {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 0.5rem !important;
    }

    .stTextInput input {
        color: var(--text-primary) !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: transparent !important;
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
    }

    .streamlit-expanderContent {
        background: var(--bg-secondary) !important;
        border: none !important;
    }

    /* Dialog/Modal */
    [data-testid="stModal"] {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 1rem !important;
    }

    /* Divider */
    hr {
        border-color: var(--border-color) !important;
        opacity: 0.5;
    }

    /* Header area spacer */
    .header-spacer {
        height: 70px;
    }

    /* Sidebar header */
    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 1rem 1rem 1rem;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 0.5rem;
    }

    .sidebar-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* New chat button */
    .new-chat-btn {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        margin: 0.5rem;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 0.5rem;
        color: var(--text-primary);
        font-size: 0.875rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .new-chat-btn:hover {
        background: var(--border-color);
    }
</style>
""",
    unsafe_allow_html=True,
)

# 3. Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []

if "brain" not in st.session_state:
    st.session_state.brain = None

if "sources" not in st.session_state:
    st.session_state.sources = []

if "api_key" not in st.session_state:
    st.session_state.api_key = ""


# 4. Settings Dialog
@st.dialog("⚙️ Settings", width="small")
def settings_dialog():
    st.markdown("### API Configuration")
    st.markdown(
        "<p style='color: #b4b4b4; font-size: 0.875rem; margin-bottom: 1rem;'>Enter your API key to enable AI responses.</p>",
        unsafe_allow_html=True,
    )

    new_api_key = st.text_input(
        "API Key",
        value=st.session_state.api_key,
        type="password",
        placeholder="sk-... or your OpenRouter key",
        label_visibility="collapsed",
    )

    st.markdown(
        "<p style='color: #8e8e8e; font-size: 0.75rem; margin-top: 0.5rem;'>Your API key is stored locally and never shared.</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("Save", use_container_width=True, type="primary"):
            st.session_state.api_key = new_api_key
            st.session_state.show_settings = False
            # Initialize brain with new key if provided
            if new_api_key:
                try:
                    st.session_state.brain = NPCBrain(api_key=new_api_key)
                except Exception:
                    pass
            st.rerun()


# 5. Two-column layout with integrated sidebar
left_col, right_col = st.columns([1, 3])

# LEFT PANEL - Documents and Controls
with left_col:
    st.markdown('<div class="left-panel">', unsafe_allow_html=True)

    # Logo Header
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 12px; padding: 0.5rem 0 1rem 0;">
            <span style="font-size: 1.75rem;">🔮</span>
            <span style="font-size: 1.25rem; font-weight: 600; color: #ececec;">Sentinel</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # New Chat Button - ChatGPT style
    if st.button(
        "➕ New Chat", key="new_chat", use_container_width=True, type="primary"
    ):
        st.session_state.messages = []
        st.toast("✅ Started new chat!")
        st.rerun()

    # Settings Button
    if st.button("⚙️ Settings", key="settings_btn", use_container_width=True):
        settings_dialog()

    st.markdown("---")

    # Documents Section Header
    st.markdown(
        "<p style='font-size: 0.75rem; color: #8e8e8e; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; font-weight: 600;'>📁 Documents</p>",
        unsafe_allow_html=True,
    )

    # File Uploader
    uploaded_files = st.file_uploader(
        "Upload PDFs",
        accept_multiple_files=True,
        type=["pdf", "txt"],
        label_visibility="collapsed",
        key="file_uploader",
        help="Upload PDF or TXT files to chat with them",
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if not any(
                s["name"] == uploaded_file.name for s in st.session_state.sources
            ):
                content = ""
                try:
                    if uploaded_file.name.endswith(".pdf"):
                        import pypdf

                        reader = pypdf.PdfReader(uploaded_file)
                        content = "\n".join(
                            [page.extract_text() for page in reader.pages]
                        )
                    else:
                        content = uploaded_file.getvalue().decode("utf-8")

                    st.session_state.sources.append(
                        {
                            "name": uploaded_file.name,
                            "content": content,
                            "active": True,
                        }
                    )

                    # Process for RAG
                    if st.session_state.api_key:
                        if not st.session_state.brain:
                            st.session_state.brain = NPCBrain(
                                api_key=st.session_state.api_key
                            )

                        with tempfile.NamedTemporaryFile(
                            delete=False,
                            suffix=os.path.splitext(uploaded_file.name)[1],
                        ) as tmp:
                            tmp.write(uploaded_file.getvalue())
                            st.session_state.brain.learn_from_file(tmp.name)
                            os.remove(tmp.name)
                        st.success(f"✓ {uploaded_file.name} processed")
                    else:
                        st.warning("Add API key in settings to enable AI")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Document List
    if st.session_state.sources:
        st.markdown(
            "<p style='font-size: 0.75rem; color: #8e8e8e; text-transform: uppercase; letter-spacing: 0.05em; padding: 0 0.5rem; margin-bottom: 0.5rem;'>Uploaded Files</p>",
            unsafe_allow_html=True,
        )

        for i, source in enumerate(st.session_state.sources):
            icon = "📄" if source["name"].endswith(".txt") else "📕"
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(
                    f"<div style='display: flex; align-items: center; gap: 8px; padding: 8px; color: #b4b4b4; font-size: 0.875rem;'>{icon} {source['name'][:25]}{'...' if len(source['name']) > 25 else ''}</div>",
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("✕", key=f"del_{i}", help="Remove"):
                    st.session_state.sources.pop(i)
                    st.rerun()
    else:
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem 1rem; color: #8e8e8e;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📁</div>
                <p style="font-size: 0.875rem; margin: 0;">No documents yet</p>
                <p style="font-size: 0.75rem; margin-top: 0.25rem;">Upload PDFs or text files</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Bottom section with API status
    api_status = "🟢 Connected" if st.session_state.api_key else "🔴 No API Key"
    st.markdown(
        f"""
        <div style='background: #2f2f2f; border: 1px solid #424242; border-radius: 12px; padding: 12px; margin-top: 1rem;'>
            <div style='display: flex; align-items: center; justify-content: space-between;'>
                <span style='font-size: 0.75rem; color: #8e8e8e; font-weight: 500;'>API STATUS</span>
                <span style='font-size: 0.75rem; color: {"#10a37f" if st.session_state.api_key else "#ef4444"};'>{api_status}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

# RIGHT PANEL - Main Chat Area
with right_col:
    # Header
    st.markdown(
        """
        <div style="text-align: center; padding: 1rem 0 2rem 0;">
            <h1 style="font-size: 2rem; font-weight: 700; color: #ececec; margin-bottom: 0.5rem;">🔮 Sentinel AI</h1>
            <p style="color: #b4b4b4; font-size: 1rem;">Intelligent Document Assistant</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        # Empty State - ChatGPT style welcome
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">
                    <span style="font-size: 2.5rem;">💬</span>
                </div>
                <h2>Start a conversation</h2>
                <p>Upload documents using the panel on the left, then ask me questions about them. I'll analyze your files and provide intelligent answers.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Suggestion chips
        st.markdown("<br>", unsafe_allow_html=True)
        suggestions = [
            "📄 Summarize my docs",
            "🔍 Find key points",
            "💡 Explain concepts",
            "📊 Compare info",
        ]

        cols = st.columns(len(suggestions))
        for i, suggestion in enumerate(suggestions):
            with cols[i]:
                if st.button(
                    suggestion, key=f"suggestion_{i}", use_container_width=True
                ):
                    st.session_state.messages.append(
                        {"role": "user", "content": suggestion}
                    )
                    st.rerun()
    else:
        # Display chat messages
        for message in st.session_state.messages:
            avatar = "👤" if message["role"] == "user" else "🔮"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input(
        "Ask anything about your documents...", key="chat_input"
    ):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message immediately
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant", avatar="🔮"):
            if not st.session_state.api_key:
                response = "👋 **Welcome!** Please add your API key in **Settings** (left panel) to start chatting."
                st.markdown(response)
            elif not st.session_state.sources:
                response = "📁 **No documents loaded.** Upload PDF or TXT files in the left panel first, then ask questions about them!"
                st.markdown(response)
            else:
                # Initialize brain if needed
                if not st.session_state.brain:
                    try:
                        with st.spinner("Initializing AI..."):
                            st.session_state.brain = NPCBrain(
                                api_key=st.session_state.api_key
                            )
                            # Process all sources
                            for source in st.session_state.sources:
                                with tempfile.NamedTemporaryFile(
                                    delete=False,
                                    suffix=".txt",
                                    mode="w",
                                    encoding="utf-8",
                                ) as tmp:
                                    tmp.write(source["content"])
                                    tmp_path = tmp.name
                                st.session_state.brain.learn_from_file(tmp_path)
                                os.remove(tmp_path)
                    except Exception as e:
                        response = f"⚠️ **Error initializing:** {str(e)}"
                        st.markdown(response)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response}
                        )
                        st.stop()

                # Get response
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.brain.ask(prompt)
                    except Exception as e:
                        response = f"⚠️ **Error:** {str(e)}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
