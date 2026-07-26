"""Export the backend's OpenAPI schema to a JSON file (no server needed).

Used by the frontend's `gen:api` script + the CI drift check (#32): the
committed ``openapi.json`` must match what the backend actually serves, and
``frontend/src/lib/api/schema.ts`` must match ``openapi.json`` - so a backend
schema change can't silently drift from the frontend types.

Usage: ``python -m app.scripts.export_openapi [path]`` (default: repo openapi.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import create_app


def export(path: str | Path) -> Path:
    schema = create_app().openapi()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    p = export(dest)
    print(f"wrote {p} ({p.stat().st_size} bytes)")
