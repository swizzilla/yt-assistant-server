from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import DEBUG
from app.database import init_db
from app.routers import oauth, whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    init_db()
    yield


app = FastAPI(
    title="YouTube WhatsApp Uploader",
    description="Upload YouTube videos via WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
    debug=DEBUG,
)

# Routers
app.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
app.include_router(whatsapp.router, prefix="/whatsapp", tags=["WhatsApp"])


@app.get("/")
async def root():
    return {"status": "running", "message": "Send 'upload' to the WhatsApp bot to start"}


@app.get("/health")
async def health():
    return {"status": "ok"}
