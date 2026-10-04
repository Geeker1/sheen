"""Load Nigeria's state and LGA boundaries (OCHA COD-AB, CC BY-IGO) into ref.admin_areas.

Ward (admin3) boundaries in this release only cover Borno, Adamawa and Yobe,
so LGA is the finest level available for the Niger Delta. See docs/DECISIONS.md.
"""

import io
import json
import zipfile
from pathlib import Path

import httpx
import structlog

from sheen.config import get_settings
from sheen.db import connect
from sheen.runs import pipeline_run

log = structlog.get_logger()

SOURCE_URL = (
    "https://data.humdata.org/dataset/81ac1d38-f603-4a98-804d-325c658599a3/resource/"
    "7e30ec96-7f29-4ee8-9f4c-77633b353cbb/download/nga_admin_boundaries.geojson.zip"
)
LEVEL_FILES = {1: "nga_admin1.geojson", 2: "nga_admin2.geojson"}


def _download(dest: Path) -> None:
    if (dest / LEVEL_FILES[2]).exists():
        return
    log.info("boundaries.download", url=SOURCE_URL)
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        resp = client.get(SOURCE_URL)
        resp.raise_for_status()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in LEVEL_FILES.values():
            zf.extract(name, dest)


def ingest() -> None:
    dest = get_settings().data_dir / "raw" / "nga_admin"
    with pipeline_run("ingest", source=SOURCE_URL) as run:
        _download(dest)
        rows = []
        for level, fname in LEVEL_FILES.items():
            for f in json.loads((dest / fname).read_text())["features"]:
                p = f["properties"]
                rows.append((
                    p[f"adm{level}_pcode"],
                    level,
                    p[f"adm{level}_name"],
                    p["adm1_pcode"] if level == 2 else None,
                    p["adm1_name"],
                    json.dumps(f["geometry"]),
                ))
        run.rows_in = len(rows)

        with connect() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE ref.admin_areas CASCADE")
            # Parents (states) sort before LGAs, satisfying the self-reference.
            cur.executemany(
                """INSERT INTO ref.admin_areas (pcode, level, name, parent_pcode, state_code, geom)
                   SELECT %s, %s, %s, %s, (SELECT code FROM ref.states WHERE name = %s),
                          ST_Multi(ST_CollectionExtract(
                              ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3))""",
                rows,
            )
            row = cur.execute("SELECT count(*) AS n FROM ref.admin_areas").fetchone()
            run.rows_out = row["n"] if row else 0
