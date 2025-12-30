import streamlit as st
import tempfile
import os
from logic.rag_engine import NPCBrain

# 1. Page Config
st.set_page_config(layout="wide", page_title="Sentinel: AI Loremaster")

# 2. Custom CSS - Dark Gaming Theme
st.markdown(
    """
<style>
    /* Main Background */
    .stApp {
        background-color: #0e1117;
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #1a1c24;
        border-right: 1px solid #00ff41;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #000000;
        color: #00ff41;
        border: 1px solid #00ff41;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #003300;
        color: #00ff41;
        border: 1px solid #00ff41;
    }
    .stButton > button:hover {
        background-color: #00ff41;
        color: #000000;
    }
    
    /* Chat Messages */
    .stChatMessage {
        background-color: #1a1c24;
        border: 1px solid #333;
    }
    
    h1, h2, h3 {
        color: #00ff41 !important;
        text-shadow: 0 0 5px #00ff41;
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

# 4. Sidebar
with st.sidebar:
    st.title("SYSTEM SETTINGS")

    api_key = st.text_input("API Key (OpenRouter/OpenAI)", type="password")

    st.markdown("---")
    st.subheader("ARCHIVES UPLOAD")

    uploaded_files = st.file_uploader(
        "Upload Game Manuals (PDF/TXT)", accept_multiple_files=True, type=["pdf", "txt"]
    )

    if uploaded_files:
        if st.button("ASSIMILATE KNOWLEDGE"):
            if not api_key:
                st.error("ACCESS DENIED: API Key required for initialization.")
            else:
                try:
                    # Initialize Brain if not exists
                    if not st.session_state.brain:
                        st.session_state.brain = NPCBrain(api_key=api_key)

                    status_area = st.empty()
                    status_area.info("INITIATING DATA ASSIMILATION...")

                    for uploaded_file in uploaded_files:
                        # Save to temp file
                        # We need to preserve extension for the ingestion logic
                        suffix = (
                            ".pdf" if uploaded_file.name.endswith(".pdf") else ".txt"
                        )

                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=suffix
                        ) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        # Ingest
                        try:
                            st.session_state.brain.learn_from_file(tmp_path)
                            status_area.success(f"PROCESSED: {uploaded_file.name}")
                        except Exception as e:
                            status_area.error(
                                f"ERROR processing {uploaded_file.name}: {e}"
                            )
                        finally:
                            # Cleanup
                            os.remove(tmp_path)

                    st.success("DATA ASSIMILATION COMPLETE.")

                except Exception as e:
                    st.error(f"SYSTEM FAILURE: {e}")

# 5. Main Chat Area
st.title("SENTINEL TERMINAL")
st.markdown("---")

# Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Query the Archives..."):
    # Render user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        if not st.session_state.brain:
            # Try to init if key exists, else error
            if api_key:
                try:
                    st.session_state.brain = NPCBrain(api_key=api_key)
                    response = st.session_state.brain.ask(prompt)
                except Exception as e:
                    response = f"SYSTEM ERROR: {e}"
            else:
                response = "ACCESS DENIED. PLEASE CONFIGURE API KEY IN SETTINGS."
        else:
            try:
                response = st.session_state.brain.ask(prompt)
            except Exception as e:
                response = f"SYSTEM FAILURE: {e}"

        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
