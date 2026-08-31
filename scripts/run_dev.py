import subprocess
import sys


def main() -> None:
    # --reload-dir scopes file-watching to app/ only -- without it, uvicorn watches the whole
    # project (including data/, frontend/, docs) and restarts the server on unrelated edits,
    # which briefly drops connections the frontend is mid-request on.
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--reload-dir", "app"]
    )
    frontend = subprocess.Popen([sys.executable, "-m", "http.server", "5500", "--directory", "frontend"])

    print("Backend:  http://127.0.0.1:8000")
    print("Frontend: http://localhost:5500")
    print("Press Ctrl+C to stop both.")

    try:
        backend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()


if __name__ == "__main__":
    main()
