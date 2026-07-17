import os
import sys

# Render auto-detects this file and runs "uvicorn main:app" from the
# backend/ directory. Adding the project root (parent of backend/) to
# sys.path makes "from backend.api.routes" importable, while the backend/
# folder itself being the cwd makes "from core.config" / "from services.*"
# importable.
_BACKEND = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_BACKEND)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

app = FastAPI(
    title="Jewellery AI Assistant",
    version="1.0"
)

# Allow frontend to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _refresh_catalog():
    # Refresh the knowledge base with the live product catalogue on boot.
    try:
        from services.catalog_sync import sync_catalog
        sync_catalog()
    except Exception:
        pass


@app.get("/")
def root():
    return {"status": "ok", "service": "Zyraluxe AI Chatbot"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
