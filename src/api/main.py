import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import appointments, auth, catalog, chat, vip, voice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("clinic_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting up Clinic AI & Royal VIP Protocol API Server...")
    yield
    log.info("Shutting down Clinic AI API Server...")


app = FastAPI(
    title="Clinic AI & Royal VIP Protocol API",
    description="Enterprise Backend for Dubai Clinic Management, AI Appointments & Royal VIP Protocols",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for Flutter Mobile, Web, and Intranet clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check probe for container orchestrators and Flutter status monitor."""
    return {
        "status": "healthy",
        "service": "clinic-ai-fastapi",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
    }


# Include modular routers
app.include_router(auth.router)
app.include_router(appointments.router)
app.include_router(catalog.router)
app.include_router(vip.router)
app.include_router(chat.router)
app.include_router(voice.router)
