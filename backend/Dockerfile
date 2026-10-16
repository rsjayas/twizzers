# Build context is the repository root (see docker-compose.yml), because the image
# also contains the admin dashboard built from ../admin.

FROM node:22-bookworm-slim AS admin-build
WORKDIR /admin
COPY admin/package.json admin/package-lock.json ./
RUN npm ci
COPY admin/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Served by the API at /admin (see app/main.py).
COPY --from=admin-build /admin/dist /admin-ui
ENV ADMIN_UI_DIR=/admin-ui

# Run as an unprivileged user (the app only reads its files).
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
