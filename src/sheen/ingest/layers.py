"""Move the mangrove and settlement data loaded by GDAL into the main tables.

scripts/load_reference_layers.sh does the GDAL part. This step repairs any
broken shapes, converts them to metres, cuts very large shapes into smaller
pieces so lookups stay fast, and records where each layer came from.
"""

import uuid
from datetime import date

import psycopg
import structlog
from psycopg import sql
from psycopg.rows import DictRow

from sheen.db import connect
from sheen.runs import pipeline_run

log = structlog.get_logger()

GMW_URL = "https://zenodo.org/records/6894273"
OSM_URL = "https://download.geofabrik.de/africa/nigeria-250101.osm.pbf"

SOURCES = {
    "mangroves_2007": ("Global Mangrove Watch v3.0, 2007 extent", GMW_URL, "CC BY 4.0", date(2007, 12, 31)),
    "mangroves_2020": ("Global Mangrove Watch v3.0, 2020 extent", GMW_URL, "CC BY 4.0", date(2020, 12, 31)),
    "settlements": ("OpenStreetMap place=* nodes (Geofabrik extract)", OSM_URL, "ODbL 1.0", date(2025, 1, 1)),
}


Conn = psycopg.Connection[DictRow]


def _staged(conn: Conn, table: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (f"stage.{table}",)).fetchone()
    return bool(row and row["ok"])


def promote() -> None:
    with pipeline_run("reference", source="stage") as run, connect() as conn:
        counts: dict[str, int] = {}

        for year in (2007, 2020):
            table = f"mangroves_{year}"
            if not _staged(conn, table):
                log.warning("layers.missing", table=table)
                continue
            conn.execute("DELETE FROM ref.mangroves WHERE year = %s", (year,))
            cur = conn.execute(
                # Only repair shapes that are broken; repairing every shape was very slow.
                sql.SQL("""INSERT INTO ref.mangroves (year, geom_utm)
                    SELECT %s, (ST_Dump(ST_Subdivide(
                               CASE WHEN ST_IsValid(g) THEN g
                                    ELSE ST_CollectionExtract(ST_MakeValid(g), 3) END, 256
                           ))).geom
                    FROM (SELECT ST_Transform(geom, 32632) AS g FROM {}) src""").format(
                    sql.Identifier("stage", table)
                ),
                (year,),
            )
            counts[table] = cur.rowcount
            _record_source(conn, table, run.run_id)

        if _staged(conn, "osm_places"):
            conn.execute("TRUNCATE ref.settlements")
            cur = conn.execute(
                """INSERT INTO ref.settlements (name, kind, geom_utm)
                   SELECT name, place, ST_Transform(geom, 32632) FROM stage.osm_places"""
            )
            counts["settlements"] = cur.rowcount
            _record_source(conn, "settlements", run.run_id)
        else:
            log.warning("layers.missing", table="osm_places")

        conn.execute("ANALYZE ref.mangroves; ANALYZE ref.settlements")
        # Mangrove area per local government area only changes with this data,
        # so it's updated here rather than on every analysis run.
        conn.execute("REFRESH MATERIALIZED VIEW ref.lga_mangroves")
        run.rows_out = sum(counts.values())
        run.details["rows"] = counts


def _record_source(conn: Conn, layer: str, run_id: uuid.UUID) -> None:
    title, url, licence, as_of = SOURCES[layer]
    conn.execute(
        """INSERT INTO ref.sources (layer, title, url, licence, as_of, loaded_run_id)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (layer) DO UPDATE
           SET title = EXCLUDED.title, url = EXCLUDED.url, licence = EXCLUDED.licence,
               as_of = EXCLUDED.as_of, loaded_run_id = EXCLUDED.loaded_run_id""",
        (layer, title, url, licence, as_of, run_id),
    )
