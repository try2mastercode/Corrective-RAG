from fastapi import FastAPI

from app.api.routes_ask import router as ask_router
from app.api.routes_documents import router as documents_router
from app.api.routes_health import router as health_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Corrective RAG", version="0.1.0")

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(ask_router)
