# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /wheels .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY src/ ./src/
COPY config/ ./config/
COPY docs/ ./docs/
COPY certs/ ./certs/

RUN useradd -m -u 1000 aiinsight && \
    chown -R aiinsight:aiinsight /app
USER aiinsight

ENV FACIS_ENV=production \
    AI_INSIGHT_HTTP__PORT=8080 \
    AI_INSIGHT_LLM__REQUIRE_HTTPS=true \
    AI_INSIGHT_RATE_LIMIT__REQUESTS_PER_MINUTE=10

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health', timeout=2)" || exit 1

CMD ["python", "-m", "src.main"]
