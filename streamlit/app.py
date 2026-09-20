import streamlit as st

st.set_page_config(page_title="Contract Risk Assistant", page_icon="⚖️")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #0E1117 0%, #1a2332 50%, #0E1117 100%);
}
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Contract Risk Assistant")
st.write("Upload a contract or Terms of Service document to check for risky clauses and ask questions about it.")

#The reset button
if "document_id" in st.session_state:
    if st.button("🔄 Start Over with a New Document"):
        for key in ["document_id", "risk_clauses", "chat_history"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


#Upload button
import requests

API_URL = "http://127.0.0.1:8000"

uploaded_file = st.file_uploader("Upload a contract (PDF)", type=["pdf"])

if uploaded_file is not None:
    if st.button("Analyze Document"):
        with st.spinner("Uploading and processing document..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            response = requests.post(f"{API_URL}/upload", files=files)

            if response.status_code == 200:
                data = response.json()
                st.session_state["document_id"] = data["document_id"]
                st.success(f"Document processed! Found {data['num_chunks']} sections.")
            else:
                st.error(f"Upload failed: {response.text}")



#Risk-summary and Q/A Chat section
if "document_id" in st.session_state:
    st.divider()

    tab1, tab2 = st.tabs(["📋 Risk Summary", "💬 Ask a Question"])

    SEVERITY_ICONS = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢"
    }

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
                    color = SEVERITY_ICONS.get(item["severity"], "#888888")
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