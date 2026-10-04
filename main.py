"""
Clinic AI & Royal VIP Protocol System Main Entrypoint
======================================================
Usage:
    python main.py
    uvicorn main:app --reload --port 8000
"""

import os
import sys
import uvicorn

from src.api.config import HOST, PORT
from src.api.main import app

# Ensure root directory is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    port = int(os.getenv("PORT", PORT))
    host = os.getenv("HOST", HOST)

    print("=" * 65)
    print("  CLINIC AI & ROYAL VIP PROTOCOL API (FASTAPI + UVICORN)")
    print(f"  Base URL     : http://localhost:{port}")
    print(f"  Swagger Docs : http://localhost:{port}/docs")
    print(f"  ReDoc Docs   : http://localhost:{port}/redoc")
    print(f"  Health Check : http://localhost:{port}/api/health")
    print("=" * 65)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
