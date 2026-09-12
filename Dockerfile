# API image for Render: Python (FastAPI) + Node (Puter bridge)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Node 20 for Puter txt2img bridge
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts/puter ./scripts/puter
COPY requirements-render.txt ./

RUN pip install -r requirements-render.txt \
    && npm ci --prefix scripts/puter

EXPOSE 8000

# Render injects PORT
CMD ["sh", "-c", "python -m initials_agent serve --host 0.0.0.0"]
