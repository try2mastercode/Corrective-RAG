import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_ask import router as ask_router
from app.api.routes_ask_agentic import router as ask_agentic_router
from app.api.routes_documents import router as documents_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_health import router as health_router
from app.api.routes_observability import router as observability_router
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Corrective RAG", version="0.1.0")


@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """A plain `@app.exception_handler(Exception)` is NOT enough here: FastAPI binds a handler
    for the bare `Exception` class to Starlette's ServerErrorMiddleware, which sits *outside*
    all user-added middleware -- including CORSMiddleware below. An exception unwinds past
    CORSMiddleware on the way up, and the resulting error response is returned directly by
    ServerErrorMiddleware without ever passing back through CORSMiddleware, so it never gets
    Access-Control-Allow-Origin added. Browsers then refuse to expose the response to
    JavaScript at all, surfacing as a generic "Failed to fetch" instead of a readable error --
    reproduced live when Groq's rate limit was exhausted mid-request. Catching the exception
    here instead, in a middleware added *before* CORSMiddleware (so CORSMiddleware ends up
    wrapping this one and still sees the response), keeps error responses inside the normal
    middleware stack so CORS headers are applied correctly."""
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": f"Internal server error: {exc}"})


# Local-first dev tool: the vanilla-JS frontend is served as static files, often from a
# different origin/port than this API (e.g. a simple static file server). Permissive CORS is
# appropriate here since this is not deployed as a public multi-tenant service. Added *after*
# the exception-catching middleware above so it wraps it (outermost middleware = last added).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(ask_router)
app.include_router(ask_agentic_router)
app.include_router(evaluation_router)
app.include_router(observability_router)
