"""Fixed exam HTTP API."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/exam", tags=["exam"])
