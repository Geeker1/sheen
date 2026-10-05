"""Download the NOSDRA spill register and save it exactly as published.

The Oil Spill Monitor website loads its data from a public address, and this
reads the same one. Nothing is cleaned here; that happens in validation.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import structlog
from psycopg.types.json import Jsonb

from sheen.config import get_settings
from sheen.db import connect
from sheen.runs import latest_hash, pipeline_run

log = structlog.get_logger()

USER_AGENT = "sheen/0.1 (research project; spill data quality analysis)"


def fetch(url: str) -> bytes:
    with httpx.Client(timeout=120, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def parse(body: bytes) -> list[dict[str, Any]]:
    records = json.loads(body)
    if not isinstance(records, list):
        raise ValueError(f"expected a JSON array, got {type(records).__name__}")
    missing_id = sum(1 for r in records if not r.get("id"))
    if missing_id:
        raise ValueError(f"{missing_id} records have no id; refusing to load")
    return records


def ingest(from_file: Path | None = None, force: bool = False) -> str | None:
    """Save a fresh download, or a saved file if one is given.

    Returns the run id, or None if the register is the same as last time
    (unless force is set), in which case nothing is saved.
    """
    s = get_settings()
    source = str(from_file) if from_file else s.nosdra_url

    with pipeline_run("ingest", source=source) as run:
        body = from_file.read_bytes() if from_file else fetch(s.nosdra_url)
        run.source_sha256 = hashlib.sha256(body).hexdigest()
        if not force and run.source_sha256 == latest_hash("ingest"):
            run.skipped = True
            return None
        records = parse(body)
        run.rows_in = len(records)

        with (
            connect() as conn,
            conn.cursor() as cur,
            cur.copy("COPY raw.spill_reports (run_id, source_id, payload) FROM STDIN") as copy,
        ):
            for r in records:
                copy.write_row((run.run_id, str(r["id"]), Jsonb(r)))
        run.rows_out = len(records)
        return str(run.run_id)
