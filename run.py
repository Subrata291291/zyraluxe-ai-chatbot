import os
import sys

# Ensure both the project root and the backend package are importable
# so that "from backend.api.routes" and "from core.config" both resolve.
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
for p in (ROOT, BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("run:app", host="0.0.0.0", port=port)
