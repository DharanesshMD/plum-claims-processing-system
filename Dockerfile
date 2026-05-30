# Multi-stage build for Next.js Frontend
FROM node:18-alpine AS frontend-builder
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
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

# Set up backend
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# Set up frontend production runtime
WORKDIR /app/frontend
COPY --from=frontend-builder /app/frontend/package*.json ./
COPY --from=frontend-builder /app/frontend/.next ./.next
COPY --from=frontend-builder /app/frontend/public ./public
RUN npm install --only=production

# Copy configurations
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create data directory for SQLite database persistence
RUN mkdir -p /app/backend/data && chmod -R 777 /app/backend/data
ENV DATABASE_URL="sqlite+aiosqlite:////app/backend/data/claims.db"

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
