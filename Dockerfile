# Single-container deployment: the API and the installable web app share one origin.
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY web_app ./web_app

ENV STATIC_DIR=/app/web_app \
    DATABASE_URL=sqlite:////app/data/billomadfx.db

RUN mkdir -p /app/data
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
