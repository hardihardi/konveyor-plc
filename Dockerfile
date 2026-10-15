FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/

# Jalankan sebagai user non-root
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV HMI_DB=/app/data/hmi.db
RUN mkdir -p /app/data && chown appuser:appuser /app/data

EXPOSE 8600

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8600/api/status', timeout=4)" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8600", "--app-dir", "backend"]
