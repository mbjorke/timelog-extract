"""
AX Domain Admin Platform — FastAPI entry point.

Start:  uvicorn main:app --reload
Docs:   http://localhost:8000/docs
Admin:  http://localhost:8000/  (admin dashboard UI)
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.admin import router as admin_router
from api.dns_records import router as dns_router
from api.domains import router as domains_router
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title=".AX Domain Admin Platform",
    description=(
        "Registrar API for .ax domains. "
        "Third-party apps use Bearer API keys to register domains and manage DNS records. "
        "All domains are automatically delegated to the platform's authoritative name servers."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domains_router)
app.include_router(dns_router)
app.include_router(admin_router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def serve_admin():
    return FileResponse(STATIC_DIR / "index.html")


@app.on_event("startup")
def on_startup():
    init_db()
    logging.getLogger(__name__).info("Database initialised.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
