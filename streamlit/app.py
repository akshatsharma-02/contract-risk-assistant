import streamlit as st

st.set_page_config(page_title="Contract Risk Assistant", page_icon="⚖️")

st.title("⚖️ Contract Risk Assistant")
st.write("Upload a contract or Terms of Service document to check for risky clauses and ask questions about it.")


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

    with tab1:
        if st.button("Generate Risk Summary"):
            with st.spinner("Analyzing clauses..."):
                response = requests.post(
                    f"{API_URL}/risk-summary",
                    json={"document_id": st.session_state["document_id"]}
                )
                if response.status_code == 200:
                    data = response.json()
                    st.write(f"**Found {data['flagged_clause_count']} potentially risky clauses:**")
                    st.markdown(data["summary"])
                else:
                    st.error(f"Failed to generate summary: {response.text}")

    with tab2:
        question = st.text_input("Ask a question about this document:")
        if st.button("Ask") and question:
            with st.spinner("Thinking..."):
                response = requests.post(
                    f"{API_URL}/ask",
                    json={"document_id": st.session_state["document_id"], "question": question}
                )
                if response.status_code == 200:
                    data = response.json()
                    st.write(data["answer"])
                else:
                    st.error(f"Failed to get answer: {response.text}")