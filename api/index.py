"""Vercel serverless entrypoint for the ResearchMind FastAPI app.

Vercel's Python runtime serves the ASGI `app` exported here. The repo's
backend package lives in backend/app, so it is added to sys.path.
On Vercel, set RESEARCHMIND_DATA_DIR=/tmp/researchmind (see vercel.json):
the filesystem is ephemeral, so this deployment is a demo — uploaded
papers persist only while the function instance lives. For persistent
use, run the backend locally or on a persistent host (see README).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
