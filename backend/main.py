"""Compatibility entry point for ``uvicorn backend.main:app``.

The canonical application lives in ``api_server.py`` so the two launch paths
cannot drift apart.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_server import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
