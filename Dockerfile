FROM python:3.12-slim

WORKDIR /app

# CPU-only PyTorch: much smaller than the default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY api/requirements.txt api-requirements.txt
COPY streamlit/requirements.txt streamlit-requirements.txt
RUN pip install --no-cache-dir -r api-requirements.txt -r streamlit-requirements.txt

# Bake the embedding model into the image so cold starts don't download it
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY api/ /app/api/
COPY streamlit/ /app/streamlit/
COPY models/transformer_final/ /app/models/transformer_final/
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

ENV MODEL_PATH=/app/models/transformer_final
ENV CHROMA_PATH=/tmp/chroma_db
ENV API_URL=http://127.0.0.1:8000

EXPOSE 8080

CMD ["/app/start.sh"]