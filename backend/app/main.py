"""
Videorama v2.0.0 - FastAPI Application
Main application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from .config import settings
from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Runs on startup and shutdown
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"📊 Database: {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials

    # Initialize database
    init_db()
    print("✅ Database initialized")

    yield

    # Shutdown
    print(f"👋 Shutting down {settings.APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Modern media library manager with AI-powered organization",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (for thumbnails, etc.)
# app.mount("/static", StaticFiles(directory="static"), name="static")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
    }


# API v1 routes
from .api.v1 import libraries, entries, import_endpoints, inbox, jobs, playlists, vhs, settings, tags

app.include_router(libraries.router, prefix="/api/v1", tags=["libraries"])
app.include_router(entries.router, prefix="/api/v1", tags=["entries"])
app.include_router(import_endpoints.router, prefix="/api/v1", tags=["import"])
app.include_router(inbox.router, prefix="/api/v1", tags=["inbox"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(playlists.router, prefix="/api/v1", tags=["playlists"])
app.include_router(vhs.router, prefix="/api/v1", tags=["vhs"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(tags.router, prefix="/api/v1", tags=["tags"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
