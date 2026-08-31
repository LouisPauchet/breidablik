# --- Frontend build stage: Node exists only here, never in the final image or at runtime ---
# Needs Node >= 22 (Nuxt 4's toolchain uses newer JS runtime features, e.g. Set.prototype.difference).
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run generate

# --- Backend runtime image ---
FROM python:3.12-slim AS backend

RUN pip install --no-cache-dir uv

WORKDIR /srv/app

COPY pyproject.toml ./
COPY app/ ./app/
COPY alembic.ini ./
RUN uv pip install --system .

COPY --from=frontend-build /frontend/.output/public ./frontend/.output/public

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
