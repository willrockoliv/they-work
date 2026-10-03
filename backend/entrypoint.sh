#!/usr/bin/env sh
# Aguarda o PostgreSQL, aplica as migrações e sobe o processo informado em CMD.
set -eu

cd /app/backend

echo "[entrypoint] aguardando PostgreSQL..."
python - <<'PY'
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import get_engine

deadline = time.monotonic() + 60
while True:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        break
    except SQLAlchemyError as exc:
        if time.monotonic() > deadline:
            print(f"[entrypoint] PostgreSQL indisponível: {exc}", file=sys.stderr)
            raise SystemExit(1)
        time.sleep(2)
print("[entrypoint] PostgreSQL pronto.")
PY

echo "[entrypoint] aplicando migrações Alembic..."
alembic upgrade head

echo "[entrypoint] iniciando: $*"
exec "$@"
