FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency file
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy source code
COPY src/ src/
COPY config/ config/
COPY data/ data/

# Download spaCy Chinese model
RUN uv run python -m spacy download zh_core_web_sm || true

EXPOSE 5005

CMD ["uv", "run", "python", "src/server.py"]
