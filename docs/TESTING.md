# Testing and verifying Sheen

Three levels, quickest first. Each step says what you should see.

## Prerequisites

- Docker (with Compose v2)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node 22 (only for the map)
- Terraform 1.9 or later (only for the infrastructure check)

```bash
uv sync              # creates .venv with the locked dependencies
cp .env.example .env # local settings (database on :5433, LocalStack S3)
```

---

## Level 1: automated checks (about a minute, no download)

```bash
make check
```

This runs ruff (lint + format), mypy in strict mode, and pytest. You should
see `Success: no issues found` from mypy and `71 passed`.

The integration tests start their own throwaway PostGIS container through
testcontainers, so Docker must be running, but you don't need `make up`.

| Test file | What it covers | Needs Docker |
|---|---|---|
| `tests/test_normalize.py` (49) | Record-level parsing: dates, quantities, causes, contaminants, state names, every coordinate format, the analysis window | No |
| `tests/test_pipeline_db.py` (13) | Ingest and validate against real PostGIS over a small synthetic geography: reprojection, corroboration, state/LGA mismatches, duplicates, DMS, out-of-window, the LGA name matcher | Yes |
| `tests/test_api.py` (9) | GraphQL queries, pagination, filters, nested fields, `explainSpill` for every location method, GeoJSON, request IDs | Yes |

Useful variations:

```bash
uv run pytest tests/test_normalize.py        # unit tests only, no Docker
uv run pytest -k duplicate -v                # one topic, verbose
uv run pytest --cov=sheen --cov-report=term-missing
```

Other checks CI runs:

```bash
docker build -t sheen:local .                       # application image
docker run --rm sheen:local sheen --help            # CLI works inside it
cd infra && terraform init -backend=false && terraform validate
cd web && npm ci && npm run build
```

---

## Level 2: run the real pipeline (20-30 minutes, about 760 MB to download)

```bash
make up migrate      # PostGIS on :5433, LocalStack S3 on :4566, schema
make reference-data  # mangrove rasters (2 x 66 MB) and OSM extract (628 MB)
make layers          # boundaries, mangroves, settlements (one-off, ~15 min)
make run             # fetch NOSDRA, validate, analyse (about a minute)
```

`make run` prints one JSON log line per step. The last three `run.succeeded`
lines should look like this:

```
stage=ingest    rows_in=21171 rows_out=21171
stage=validate  rows_in=21171 rows_out=20443  out_of_window=728  analysable=13334
stage=analyse   rows_out=13334
```

> The live NOSDRA register changes over time, so counts may drift from the
> figures in FINDINGS.md. To reproduce them exactly, run against the saved
> snapshot: `uv run --env-file .env sheen run --from-file data/raw/nosdra_snapshot.json`.
> Snapshots are also archived to S3 (LocalStack locally) under `nosdra/`.

### Check the results in the database

Open a SQL shell:

```bash
docker compose exec db psql -U sheen -d sheen
```

```sql
-- Every stage run, newest first: status, row counts, timings
SELECT stage, status, rows_in, rows_out, round(extract(epoch FROM finished_at - started_at)) AS secs
FROM ops.pipeline_runs ORDER BY started_at DESC LIMIT 6;

-- Issue counts by type (QUANTITY_MISSING about 7.8k and COORD_MISSING about 4.6k at the top)
SELECT code, severity, count(*) FROM clean.spill_issues GROUP BY 1, 2 ORDER BY 3 DESC;

-- How each location was obtained
SELECT geom_method, count(*) FROM clean.spills GROUP BY 1 ORDER BY 2 DESC;

-- Recovered coordinates: what was published and where it ended up
SELECT s.spill_id, s.lga_reported, a.name AS located_in, i.message
FROM clean.spill_issues i
JOIN clean.spills s USING (spill_id)
LEFT JOIN ref.admin_areas a ON a.pcode = s.lga_pcode
WHERE i.code IN ('COORD_REPROJECTED', 'COORD_DMS_PARSED', 'COORD_DECIMAL_SHIFTED');

-- Operator reporting completeness
SELECT operator, reports, share_unplaceable, share_missing_quantity
FROM analysis.operator_quality WHERE reports >= 150 ORDER BY reports DESC;

-- The LGA name matcher
SELECT ref.lga_name_similarity('Ukwa West', 'Ukwa East'),   -- 0: different twins
       ref.lga_name_similarity('DEYEMA', 'Degema');         -- 0.4: a typo, matches
```

### Spot-check specific records

These records each show one validation rule at work. Look them up with
`explainSpill` (below) or in SQL.

| Spill | What to look for |
|---|---|
| `281734` | Published as `04505482, 006281269`; parsed as packed DMS into Abua/Odual, Rivers |
| `145909` | Grid metres with no state given; placed in Bonny, next to the reported Okrika, not in Oyo |
| `279988` | Reported in Abia/Ukwa West; the East-Belt reading is chosen because it lands in Abia |
| `190484` | Grid metres reprojected with EPSG:26392 into Degema, matching the report |
| `236565` | `495259733, 685983183`: no reading fits, so it's `COORD_UNRESOLVED` rather than guessed |

---

## Level 3: the API and the map

```bash
make api   # http://localhost:8000/graphql opens GraphiQL
make web   # http://localhost:5173 (in a second terminal)
```

Queries to paste into GraphiQL:

```graphql
# Trace one record from the raw JSON to its result
{
  explainSpill(id: "281734") {
    steps { step outcome }
    spill { issues { code severity message } }
    rawRecord
  }
}
```

```graphql
# Filter + cursor pagination; run again with after: "<endCursor>"
{
  spills(filter: { issueCode: "COORD_REPROJECTED" }, first: 5) {
    totalCount hasNextPage endCursor
    items { id operator incidentDate locationMethod lga { name stateName } }
  }
}
```

```graphql
# Summaries
{
  summary { reportsInWindow analysable reportedBbl }
  lgas(stateCode: "RI", limit: 5) { name spills reportedBbl mangroveHa2020 mangroveChangePct }
  issueTypes { code severity count }
  pipelineRuns(limit: 3) { stage status rowsOut details }
}
```

Plain HTTP endpoints:

```bash
curl -i localhost:8000/healthz                       # {"status":"ok"} + an x-request-id header
curl -s localhost:8000/geojson/lgas | head -c 300    # GeoJSON for the choropleth
curl -s "localhost:8000/geojson/spills?state_code=BY" | head -c 300
```

On the map you should see:

- LGAs shaded by spill count, darkest in Southern Ijaw (Bayelsa)
- spill points tracing pipeline routes; hollow points are corrected locations
- the "Mangrove change 2007-2020" toggle recolouring the LGAs
- clicking a spill showing its treatment steps, issues and raw record

The API logs one JSON line per request with a `request_id`. Send your own
with `-H 'x-request-id: test123'` and find it in the logs.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` on port 5433 | `make up`; wait for `docker compose ps` to show the db as healthy |
| Migration fails right after the first `make up` | Postgres restarts once during first initialisation; run `make migrate` again |
| `No successful spill ingest found` | Run `sheen ingest spills` (or `make run`) before `sheen validate` |
| Integration tests skipped | Docker isn't running or not on `PATH` |
| Map is empty | The API must be running on :8000 (`make api`); check the browser console |
| `archive.failed` warning in logs | The local S3 isn't up (`docker compose up -d s3`). Archiving is best-effort, so ingestion still succeeds |
