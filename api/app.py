from fastapi import FastAPI
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from sentence_transformers import SentenceTransformer
import torch
from dotenv import load_dotenv
import os
from google import genai
import re

load_dotenv("../.env")
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

app = FastAPI(title="Contract Risk Assistant API")

LABEL_NAMES = ['Limitation of liability', 'Unilateral termination', 'Unilateral change',
               'Content removal', 'Contract by using', 'Choice of law', 'Jurisdiction', 'Arbitration']

print("Loading classifier model...")
classifier_model = AutoModelForSequenceClassification.from_pretrained("../models/transformer_final")
classifier_tokenizer = AutoTokenizer.from_pretrained("../models/transformer_final")

print("Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

print("All models loaded. API ready.")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "API is running"}


#Adding a real end-point(/classify)
from pydantic import BaseModel

class ClassifyRequest(BaseModel):
    text: str

class ClassifyResponse(BaseModel):
    flagged_categories: dict


@app.post("/classify")
def classify_text(request: ClassifyRequest):
    inputs = classifier_tokenizer(
        request.text,
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt"
    )
    with torch.no_grad():
        outputs = classifier_model(**inputs)
    probabilities = torch.sigmoid(outputs.logits).numpy()[0]

    flagged = {
        LABEL_NAMES[i]: float(probabilities[i])
        for i in range(len(LABEL_NAMES))
        if probabilities[i] > 0.5
    }

    return ClassifyResponse(flagged_categories=flagged)



#Uploading Document+ RAG endpoints(/upload)
from fastapi import UploadFile, File
from pypdf import PdfReader
import chromadb
import re

chroma_client = chromadb.PersistentClient(path="../data/chroma_db")

def extract_text_from_pdf_bytes(pdf_bytes):
    reader = PdfReader(pdf_bytes)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text, chunk_size=100, overlap=20):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


@app.post("/upload")
def upload_document(file: UploadFile = File(...)):
    pdf_bytes = file.file
    text = extract_text_from_pdf_bytes(pdf_bytes)
    chunks = chunk_text(text)
    embeddings = embedding_model.encode(chunks)

    document_id = file.filename.replace(".pdf", "").replace(" ", "_")
    collection = chroma_client.get_or_create_collection(name=document_id)
    collection.add(
        documents=chunks,
        embeddings=embeddings.tolist(),
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )

    return {"document_id": document_id, "num_chunks": len(chunks)}


#Now the entire RAG loop(/ask)
class AskRequest(BaseModel):
    document_id: str
    question: str

class AskResponse(BaseModel):
    answer: str


@app.post("/ask")
def ask_document(request: AskRequest):
    collection = chroma_client.get_collection(name=request.document_id)

    question_embedding = embedding_model.encode([request.question]).tolist()
    results = collection.query(
        query_embeddings=question_embedding,
        n_results=2
    )
    retrieved_chunks = results["documents"][0]

    context = "\n\n".join(retrieved_chunks)
    prompt = f"""You are a legal assistant helping someone understand a contract.
Answer the user's question using ONLY the context provided below.
If the context doesn't contain enough information to answer, say so clearly rather than guessing.

Context:
{context}

Question: {request.question}

Answer:"""

    answer_text = call_gemini_with_retry(prompt)
    return AskResponse(answer=answer_text)


#Adding the Risk Summary feature(/risk-summary)
class RiskSummaryRequest(BaseModel):
    document_id: str

class RiskSummaryResponse(BaseModel):
    clauses: list
    flagged_clause_count: int


def split_into_sentences(text):
    text = text.replace("\n", " ")
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.split()) >= 5]
    return sentences

#Catches sentences that are near duplicate
def deduplicate_sentences(sentences):
    sentences_sorted = sorted(sentences, key=len, reverse=True)
    kept = []
    for s in sentences_sorted:
        if not any(s in longer for longer in kept):
            kept.append(s)
    return [s for s in sentences if s in kept]



import json

@app.post("/risk-summary")
def get_risk_summary(request: RiskSummaryRequest):
    collection = chroma_client.get_collection(name=request.document_id)
    all_data = collection.get()
    full_text = " ".join(all_data["documents"])
    sentences = split_into_sentences(full_text)
    sentences = deduplicate_sentences(sentences)

    inputs = classifier_tokenizer(
        sentences, padding=True, truncation=True, max_length=128, return_tensors="pt"
    )
    with torch.no_grad():
        outputs = classifier_model(**inputs)
    probabilities = torch.sigmoid(outputs.logits).numpy()

    flagged_clauses = []
    for i, sentence in enumerate(sentences):
        flagged_labels = [LABEL_NAMES[j] for j in range(len(LABEL_NAMES)) if probabilities[i][j] > 0.5]
        if flagged_labels:
            flagged_clauses.append({"sentence": sentence, "labels": flagged_labels})

    if not flagged_clauses:
        return RiskSummaryResponse(clauses=[], flagged_clause_count=0)

    clauses_text = ""
    for item in flagged_clauses:
        clauses_text += f"- Clause: \"{item['sentence']}\"\n  Flagged as: {', '.join(item['labels'])}\n\n"

    prompt = f"""You are a legal assistant analyzing risky contract clauses.

Below are clauses flagged as potentially unfair, with their category.

{clauses_text}

For each clause, respond with a JSON array. Each element must have exactly these fields:
- "clause": the original clause text (shortened to under 100 characters if needed)
- "category": the flagged category
- "explanation": a 1-2 sentence plain-English explanation of what it means and why it matters
- "severity": one of "high", "medium", or "low" based on how much it could harm the average consumer

Respond with ONLY the JSON array, no other text, no markdown code fences."""

    raw_response = call_gemini_with_retry(prompt)

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    parsed_clauses = json.loads(cleaned)

    return RiskSummaryResponse(clauses=parsed_clauses, flagged_clause_count=len(flagged_clauses))



#Handle when Error:503(Google server overloaded)
import time
def call_gemini_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise