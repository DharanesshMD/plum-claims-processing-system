"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.claims import router as claims_router
from app.api.documents import router as documents_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-powered multi-agent health insurance claims processing system",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(claims_router)
app.include_router(documents_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "message": "Plum Claims Processing System",
        "docs": "/docs",
        "health": "/health",
    }
