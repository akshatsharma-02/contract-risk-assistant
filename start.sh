#!/bin/bash
set -e

echo "Starting FastAPI backend..."
cd /app/api
uvicorn app:app --host 127.0.0.1 --port 8000 &

echo "Waiting for backend to finish loading models..."
python - <<'EOF'
import time, urllib.request
for _ in range(120):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/", timeout=2)
        print("Backend is ready.")
        break
    except Exception:
        time.sleep(1)
else:
    print("Backend not ready in time; starting Streamlit anyway.")
EOF

echo "Starting Streamlit on port ${PORT:-8080}..."
cd /app/streamlit
exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8080}" \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false