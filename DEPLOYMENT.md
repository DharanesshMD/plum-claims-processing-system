# Deployment Guide: Plum Claims Processing System

This guide outlines the production deployment process for the **Plum Claims Processing System** (FastAPI backend + Next.js frontend + SQLite database). 

---

## 🏗️ Deployment Architecture

To simplify hosting and eliminate Cross-Origin Resource Sharing (CORS) issues, the entire application is packaged into a **single, unified Docker container**:

```mermaid
graph TD
    Client([User Browser]) -->|Port 8080 (HTTP/HTTPS)| Nginx[Nginx Reverse Proxy]
    Nginx -->|/api/* requests| FastAPI[FastAPI Backend - Port 8000]
    Nginx -->|Other requests| NextJS[Next.js Frontend - Port 3000]
    FastAPI -->|SQLite| DB[(In-Memory SQLite)]
    Supervisord[Supervisor Process Manager] -->|Manages| Nginx
    Supervisord -->|Manages| FastAPI
    Supervisord -->|Manages| NextJS
```

- **Nginx (Port 8080)**: Serves as the public-facing entrypoint, reverse-proxying `/api` requests to the FastAPI backend and all other paths to the Next.js frontend.
- **Supervisor**: Runs as the main container process, managing and keeping the three child processes (FastAPI, Next.js, Nginx) running.
- **SQLite Database**: Set up as an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) to ensure high-performance, stateless serverless operation.

---

## 🐳 Running Locally with Docker

You can build and run the unified container locally on your machine using Docker.

### 1. Build the local image:
```bash
docker build -t plum-claims-system:local .
```

### 2. Run the container:
```bash
docker run -d \
  -p 8080:8080 \
  -e LLM_PROVIDER="cursor" \
  -e CURSOR_API_KEY="your_api_key_here" \
  -e CURSOR_MODEL="gpt-5.4-nano" \
  -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  --name plum-claims-container \
  plum-claims-system:local
```
The application will be available at [http://localhost:8080](http://localhost:8080).

---

## 🚀 Google Cloud Run Production Deployment

Google Cloud Run is the recommended platform for deploying this application. It provides an automated serverless container hosting environment with automated HTTPS, traffic routing, and scale-to-zero capabilities.

### Prerequisites

Ensure you have the Google Cloud SDK (`gcloud` CLI) installed and authenticated:
```bash
# Authenticate gcloud CLI
gcloud auth login

# Set active project
gcloud config set project plum-claims
```

### Step 1: Push the Docker Image to Artifact Registry

Because Google Cloud Run deployments run on Google's managed servers, we must build the image for the target architecture (`linux/amd64`) and push it to Google Artifact Registry:

```bash
# 1. Build and tag the image for linux/amd64
docker build --platform linux/amd64 -t asia-south1-docker.pkg.dev/plum-claims/my-docker-repo/plum-claims-system:latest .

# 2. Push the tagged image to Google Artifact Registry
docker push asia-south1-docker.pkg.dev/plum-claims/my-docker-repo/plum-claims-system:latest
```

### Step 2: Deploy to Google Cloud Run

Deploy the container image to Cloud Run using the `gcloud run deploy` command:

```bash
gcloud run deploy plum-claims-service \
  --image=asia-south1-docker.pkg.dev/plum-claims/my-docker-repo/plum-claims-system:latest \
  --region=asia-south1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080
```

### Step 3: Configure Environment Variables

For the application to function correctly, configure the required environment variables in the Cloud Run service configuration:

```bash
gcloud run services update plum-claims-service \
  --region=asia-south1 \
  --update-env-vars="LLM_PROVIDER=cursor,CURSOR_API_KEY=your_cursor_api_key,CURSOR_MODEL=gpt-5.4-nano,DATABASE_URL=sqlite+aiosqlite:///:memory:,PYTHONUNBUFFERED=1"
```

- `LLM_PROVIDER`: Set to `cursor` (or `nvidia`).
- `CURSOR_API_KEY`: The API key to access Cursor model APIs.
- `CURSOR_MODEL`: The model name (e.g. `gpt-5.4-nano`).
- `DATABASE_URL`: Set to `sqlite+aiosqlite:///:memory:` for in-memory database storage (resolving file locking issues and avoiding external dependencies).
- `PYTHONUNBUFFERED`: Set to `1` to output Python prints/logs immediately in Google Cloud Logging.

---

## ⚡ Cold Start 502 Gateway Resolution

When Cloud Run scales down to `0` instances, the next incoming request triggers a **cold start**. 

### The Problem
During a cold start, Nginx starts up instantly and binds to the container port (`8080`). Cloud Run detects port `8080` is active and immediately routes incoming client traffic to the container. However, Next.js (port `3000`) and FastAPI (port `8000`) take a few seconds to finish booting. Nginx returns a `502 Bad Gateway` error for all client requests routed during this delay.

### The Fix
To prevent this, the container includes a TCP readiness check script: [wait_for_services.py](file:///Users/dharun/Personal/Projects/Plum%20Assignment%20-%2012-04-2026/wait_for_services.py).

In the Supervisor configuration [supervisord.conf](file:///Users/dharun/Personal/Projects/Plum%20Assignment%20-%2012-04-2026/supervisord.conf), the Nginx command is modified to block Nginx startup until both backend and frontend ports are ready:
```ini
[program:nginx]
command=bash -c "python3 /app/wait_for_services.py && exec nginx -g 'daemon off;'"
```

This guarantees that Cloud Run's container startup probe will wait to mark the container ready until both Next.js and FastAPI are fully functional, eliminating the `502 Bad Gateway` error on cold starts.
