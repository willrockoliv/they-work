# Backend FastAPI do TheyWork. Build context = raiz do repositório.
FROM python:3.14.8-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Camada de dependências: invalidada apenas quando o pyproject muda.
COPY pyproject.toml README.md ./
COPY backend/app/__init__.py ./backend/app/__init__.py
RUN pip install --no-cache-dir "."

COPY backend ./backend

# Alembic e Uvicorn esperam rodar a partir da raiz do backend.
WORKDIR /app/backend

RUN useradd --create-home --uid 10001 theywork \
    && chmod +x /app/backend/entrypoint.sh \
    && chown -R theywork:theywork /app
USER theywork

EXPOSE 8000

# Healthcheck sem dependências extras no sistema.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/app/backend/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
