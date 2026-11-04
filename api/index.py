"""Vercel serverless entry point.

Vercel's Python runtime serves the FastAPI app from here; the application
code itself lives in ../backend. On Vercel every non-file request lands on
this app, so it also serves the built frontend (../frontend/dist, which
`npm run build` produces during the Vercel build). Locally you can ignore
this file and just run uvicorn (see README).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402


@app.middleware("http")
async def _cache_headers(request, call_next):
    """Vite assets are content-fingerprinted, so browsers can keep them
    for a year; without this they were served max-age=0 and revalidated
    (through the Python function) on every page load. The HTML shell is
    the opposite: always revalidate so a new deploy shows up at once.
    API JSON is left untouched.
    """
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


_DIST = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)

if os.path.isdir(_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    def _spa_fallback(full_path: str):
        return FileResponse(os.path.join(_DIST, "index.html"))
