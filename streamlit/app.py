
import base64
import os
import time
 
import requests
import streamlit as st
 
# set_page_config must be the very first Streamlit command
st.set_page_config(page_title="Contract Risk Assistant", page_icon="⚖️")
 
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
 
SEVERITY_COLORS = {
    "high": "#D64545",
    "medium": "#D6A845",
    "low": "#4A9D6E",
}
SEVERITY_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}
 
 
# ---------- Background image ----------
def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()
 
 
bg_image = get_base64_image("static/background.jpg")
 
st.markdown(f"""
<style>
:root {{
    --bg-img: url("data:image/jpeg;base64,{bg_image}");
    --overlay: linear-gradient(rgba(8,11,16,0.72), rgba(8,11,16,0.85));
    --bar-bg: rgba(8,11,16,0.88);
    --bar-text: #FAFAFA;
    --bar-line: rgba(201,161,92,0.45);
}}
@media (prefers-color-scheme: light) {{
    :root {{
        --overlay: linear-gradient(rgba(250,250,252,0.90), rgba(244,246,250,0.94));
        --bar-bg: rgba(255,255,255,0.90);
        --bar-text: #1B2230;
        --bar-line: rgba(138,108,58,0.45);
    }}
}}
.stApp {{
    background-image: var(--overlay), var(--bg-img);
    background-size: cover;
    background-position: center 30%;
    background-attachment: fixed;
    background-repeat: no-repeat;
}}
header[data-testid="stHeader"] {{
    background: var(--bar-bg);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--bar-line);
}}
header[data-testid="stHeader"]::before {{
    content: "⚖️  Contract Risk Assistant";
    position: absolute;
    left: 1.25rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.2px;
    color: var(--bar-text);
    white-space: nowrap;
    pointer-events: none;
}}
@media (max-width: 480px) {{
    header[data-testid="stHeader"]::before {{
        font-size: 0.9rem;
        left: 0.75rem;
    }}
}}
</style>
""", unsafe_allow_html=True)
 
st.title("⚖️ Contract Risk Assistant")
st.write("Upload a contract or Terms of Service document to check for risky clauses and ask questions about it.")
 
 
# ---------- Backend warm-up check ----------
def backend_ready():
    try:
        return requests.get(f"{API_URL}/", timeout=2).status_code == 200
    except requests.exceptions.RequestException:
        return False
 
 
# Once the backend has answered, remember it so we don't re-check on every rerun
if not st.session_state.get("backend_ready"):
    if backend_ready():
        st.session_state["backend_ready"] = True
    else:
        st.info("⏳ The analysis engine is warming up. This can take a minute or two on first load.")
        time.sleep(5)
        st.rerun()
 
 
# ---------- Session state setup ----------
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
 
 
# ---------- Reset button ----------
if "document_id" in st.session_state:
    if st.button("🔄 Start Over with a New Document"):
        for key in ["document_id", "risk_clauses", "chat_history"]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state["uploader_key"] += 1
        st.rerun()
 
 
# ---------- Upload ----------
uploaded_file = st.file_uploader(
    "Upload a contract (PDF)",
    type=["pdf"],
    key=f"uploader_{st.session_state['uploader_key']}"
)
 
if uploaded_file is not None:
    if st.button("Analyze Document"):
        with st.spinner("Uploading and processing document..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            response = requests.post(f"{API_URL}/upload", files=files)
 
            if response.status_code == 200:
                data = response.json()
                st.session_state["document_id"] = data["document_id"]
                st.success("Document ready. Generate a risk summary or ask a question below.")
            else:
                st.error(f"Upload failed: {response.text}")
 
 
# ---------- Risk summary and Q/A chat ----------
if "document_id" in st.session_state:
    st.divider()
 
    tab1, tab2 = st.tabs(["📋 Risk Summary", "💬 Ask a Question"])
 
    with tab1:
        if st.button("Generate Risk Summary"):
            with st.spinner("Analyzing clauses..."):
                response = requests.post(
                    f"{API_URL}/risk-summary",
                    json={"document_id": st.session_state["document_id"]}
                )
                if response.status_code == 200:
                    st.session_state["risk_clauses"] = response.json()["clauses"]
                else:
                    st.error(f"Failed to generate summary: {response.text}")
 
        if "risk_clauses" in st.session_state:
            clauses = st.session_state["risk_clauses"]
            st.write(f"**Found {len(clauses)} potentially risky clauses:**")
 
            for item in clauses:
                color = SEVERITY_COLORS.get(item["severity"], "#888888")
                icon = SEVERITY_ICONS.get(item["severity"], "⚪")
                with st.expander(f"{icon} {item['category']} — {item['severity'].upper()} risk"):
                    card_html = f"""
                    <div style='border-left: 4px solid {color}; padding-left: 12px; margin-bottom: 8px;'>
                        <p style='color: {color}; font-weight: bold; margin-bottom: 4px;'>{item['severity'].upper()} RISK</p>
                        <p><strong>Clause:</strong> <em>"{item['clause']}"</em></p>
                        <p><strong>Why it matters:</strong> {item['explanation']}</p>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
 
    with tab2:
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
 
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
 
        question = st.chat_input("Ask a question about this document...")
 
        if question:
            st.session_state["chat_history"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.write(question)
 
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = requests.post(
                        f"{API_URL}/ask",
                        json={"document_id": st.session_state["document_id"], "question": question}
                    )
                    if response.status_code == 200:
                        answer = response.json()["answer"]
                        st.write(answer)
                        st.session_state["chat_history"].append({"role": "assistant", "content": answer})
                    else:
                        st.error(f"Failed to get answer: {response.text}")
 
