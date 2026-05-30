# Multi-stage build for Next.js Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# Build frontend with relative API path
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# Final Stage: Python 3.12 with Node and Nginx
FROM python:3.12-slim

# Install system dependencies, Node.js (for Next.js runtime), Nginx, and Supervisor
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

# Set up backend
WORKDIR /app/backend
COPY backend/pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install --no-cache-dir .
COPY backend/ ./
RUN pip install --no-cache-dir .


# Set up frontend production runtime
WORKDIR /app/frontend
COPY --from=frontend-builder /app/frontend/package*.json ./
COPY --from=frontend-builder /app/frontend/.next ./.next
COPY --from=frontend-builder /app/frontend/public ./public
RUN npm install --only=production

# Copy configurations
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY test_cases.json /app/test_cases.json
COPY policy_terms.json /app/policy_terms.json

# Create data directory for SQLite database persistence
RUN mkdir -p /app/backend/data && chmod -R 777 /app/backend/data
ENV DATABASE_URL="sqlite+aiosqlite:////app/backend/data/claims.db"

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
