FROM node:22-alpine AS react-build

WORKDIR /frontend
COPY frontend-react/package.json frontend-react/package-lock.json ./
RUN npm ci
COPY frontend-react ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY evaluation ./evaluation
COPY assets ./assets
COPY docs ./docs
COPY app.html index.html ASSETS.md ./
COPY --from=react-build /frontend/dist ./frontend-react-dist

RUN pip install --upgrade pip && pip install ".[api]"

RUN mkdir -p /app/reports/history /app/storage && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn legacydb_copilot.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
