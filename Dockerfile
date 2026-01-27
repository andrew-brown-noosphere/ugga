# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

# Cache bust: update this value to force frontend rebuild
ARG FRONTEND_CACHE_BUST=2026-01-26-v9
COPY frontend/ ./

# Clerk publishable key (public - safe to include)
RUN echo "VITE_CLERK_PUBLISHABLE_KEY=pk_test_aGFwcHktd2FscnVzLTUwLmNsZXJrLmFjY291bnRzLmRldiQ" > .env

RUN npm run build

# Stage 2: Python backend + serve frontend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./static

# Create data directory
RUN mkdir -p /app/data

# Set Python path
ENV PYTHONPATH=/app

# Expose port (Railway uses PORT env var)
EXPOSE 8000

# Run the API with uvicorn
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
