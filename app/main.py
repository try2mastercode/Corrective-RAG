from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_ask import router as ask_router
from app.api.routes_documents import router as documents_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_health import router as health_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="Corrective RAG", version="0.1.0")

# Local-first dev tool: the vanilla-JS frontend is served as static files, often from a
# different origin/port than this API (e.g. a simple static file server). Permissive CORS is
# appropriate here since this is not deployed as a public multi-tenant service.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(ask_router)
app.include_router(evaluation_router)
