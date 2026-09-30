FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; AutoModelForSequenceClassification.from_pretrained('akshat-02/contract-risk-classifier'); AutoTokenizer.from_pretrained('akshat-02/contract-risk-classifier')"

ENV MODEL_PATH=akshat-02/contract-risk-classifier
ENV CHROMA_PATH=/tmp/chroma_db
ENV ENV_PATH=/app/.env

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]