from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
# raise_server_exceptions=False: TestClient re-raises unhandled exceptions into the test by
# default (a debugging convenience) instead of returning the actual HTTP response our custom
# exception handler produces. A real server (uvicorn) never does this -- disable it here so
# this test exercises the real response path, the same one a browser actually receives.
client_no_raise = TestClient(app, raise_server_exceptions=False)


@app.get("/__test_only_boom")
async def _boom():
    raise RuntimeError("boom")


def test_unhandled_exception_still_carries_cors_headers():
    """Regression test: an unhandled exception (e.g. an LLM provider error after exhausting
    retries) must not fall through to Starlette's bare default error handling, which skips
    CORSMiddleware entirely -- browsers then refuse to expose the response to JavaScript at
    all, surfacing as a generic 'Failed to fetch' instead of a readable error. Found live when
    Groq's rate limit was exhausted mid-request."""
    response = client_no_raise.get("/__test_only_boom", headers={"Origin": "http://localhost:5500"})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == "*"
    assert "Internal server error" in response.json()["detail"]


def test_normal_success_response_still_carries_cors_headers():
    response = client.get("/health", headers={"Origin": "http://localhost:5500"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
