"""Keep a record of every pipeline run.

The record is saved before the work starts, so even a run that crashes
leaves a trace.
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog
from psycopg.types.json import Jsonb

from sheen.db import connect

log = structlog.get_logger()


@dataclass
class Run:
    run_id: uuid.UUID
    stage: str
    rows_in: int | None = None
    rows_out: int | None = None
    source_sha256: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@contextmanager
def pipeline_run(
    stage: str,
    *,
    source: str | None = None,
    ruleset_version: str | None = None,
    parent_run_id: uuid.UUID | None = None,
) -> Iterator[Run]:
    run = Run(run_id=uuid.uuid4(), stage=stage)
    with connect() as conn:
        conn.execute(
            """INSERT INTO ops.pipeline_runs (run_id, stage, source, ruleset_version, parent_run_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (run.run_id, stage, source, ruleset_version, parent_run_id),
        )

    structlog.contextvars.bind_contextvars(run_id=str(run.run_id), stage=stage)
    started = time.monotonic()
    log.info("run.started", source=source, ruleset_version=ruleset_version)
    try:
        yield run
    except Exception as exc:
        _finish(run, "failed", error=f"{type(exc).__name__}: {exc}")
        log.exception("run.failed", duration_s=round(time.monotonic() - started, 2))
        raise
    else:
        _finish(run, "succeeded")
        log.info(
            "run.succeeded",
            rows_in=run.rows_in,
            rows_out=run.rows_out,
            duration_s=round(time.monotonic() - started, 2),
            **run.details,
        )
    finally:
        structlog.contextvars.unbind_contextvars("run_id", "stage")


def _finish(run: Run, status: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """UPDATE ops.pipeline_runs
               SET status = %s, rows_in = %s, rows_out = %s, source_sha256 = %s,
                   details = %s, error = %s, finished_at = now()
               WHERE run_id = %s""",
            (status, run.rows_in, run.rows_out, run.source_sha256, Jsonb(run.details), error, run.run_id),
        )


def latest_successful(stage: str) -> uuid.UUID | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT run_id FROM ops.pipeline_runs
               WHERE stage = %s AND status = 'succeeded'
               ORDER BY finished_at DESC LIMIT 1""",
            (stage,),
        ).fetchone()
    return row["run_id"] if row else None
