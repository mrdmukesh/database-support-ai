FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY assets ./assets
COPY app.html index.html ASSETS.md ./

RUN pip install --upgrade pip && pip install ".[api]"

RUN mkdir -p /app/reports/history /app/storage && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn legacydb_copilot.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
