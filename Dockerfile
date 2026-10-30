# Imagen del servidor del juego (FastAPI + WebSocket). La usan docker compose y Render.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
# El esquema del E2: el servidor lo crea si la base está vacía
COPY docs/modelos/sql ./sql
ENV JUEGO_SQL=/app/sql PYTHONUNBUFFERED=1
EXPOSE 8000
# Un solo proceso: las partidas en curso viven en memoria (ver README, "Limitaciones")
CMD ["sh", "-c", "uvicorn juegocartas.arranque:app --host 0.0.0.0 --port ${PORT:-8000}"]
