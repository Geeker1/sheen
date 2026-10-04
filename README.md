# Sheen

A data pipeline and API for Nigeria's official oil spill register. It
ingests the National Oil Spill Detection and Response Agency's (NOSDRA)
reports, checks every record for problems, recovers locations published in
the wrong format, and measures what lay near each spill (mangroves,
settlements) at local government area (LGA) level.

<!--
  TODO (author): 2-3 sentences in your own words on why this matters to you,
  e.g. growing up in Port Harcourt, what spills meant for people you know.
  Keep it specific and short; the rest of the README is technical.
-->

![Map of validated spill reports, LGAs shaded by spill count](docs/img/map.png)

## What it found

From 20,443 reports dated 2005–2024 ([full findings](docs/FINDINGS.md)):

- **65% are usable for spatial analysis.** 23% have no usable location and
  9% are recorded as "no spill" in a spill register.
- **Coordinates come in at least four formats:** decimal degrees, Nigerian
  grid metres in three Minna belts and UTM, packed degrees-minutes-seconds,
  and misplaced decimals. 40 records were recovered, each only when the
  report's own state backs up the fix.
- **Reporting completeness varies a lot by operator:** from 0% of reports
  without a location (Heritage) to 30% (SPDC) and 65% (Chevron).
- **No detectable link at LGA scale between spill density and mangrove
  extent loss.** This is a limit of what extent maps can show, not evidence
  of no harm (see findings §6).

## How it works

```
NOSDRA JSON ──► raw.spill_reports ──► validate ──► clean.spills ──► analyse ──► analysis.*
  (weekly)       append-only, +S3      │            + spill_issues     │          exposure,
                 SHA-256 per run       │                               │          LGA/operator
                                       ▼                               ▼          summaries
                             Python record checks            PostGIS: mangroves     │
                             + candidate coordinate          within 1 km, OSM       ▼
                             fixes ──► PostGIS picks the     settlements    GraphQL API + GeoJSON
                             one the report corroborates                    ──► map (React/MapLibre)

ops.pipeline_runs: one row per stage run (row counts, source hash, ruleset
version, per-step timings, error). Every clean/analysis row carries a run_id.
```

- **Validation** ([issues catalogue](src/sheen/validation/issues.py)): 29
  typed issue codes in three severities. `error` excludes a record from
  analysis but keeps it; `warning` flags it; `info` records a correction.
  Thresholds live in a versioned ruleset ([rules/v1.yaml](rules/v1.yaml)),
  and each result records the version that produced it.
- **Coordinate recovery**: the record-level pass proposes every plausible
  reading; PostGIS keeps the one that lands in the reported state (or near
  the reported LGA) and inside its projection's zone. See
  [DECISIONS.md](docs/DECISIONS.md#coordinate-corrections) for how this rule
  was arrived at, including the bugs that shaped it.
- **`explainSpill(id)`** traces any record from the raw published JSON
  through each decision to its analysis result. It is what you'd use to
  answer "why does this spill look wrong?"

## Stack

Python 3.12 · FastAPI + Strawberry GraphQL · psycopg 3 (plain SQL, no ORM) ·
PostgreSQL 16 + PostGIS 3.4 · Alembic · GDAL (reference layers) · pytest +
testcontainers · Docker · Terraform (AWS: ECS Fargate, RDS, S3, ECR, ALB,
EventBridge Scheduler, CloudWatch) · GitHub Actions · React + MapLibre.

## Run it

Needs Docker, [uv](https://docs.astral.sh/uv/), Node 22.

```bash
make up migrate          # PostGIS + local S3 (LocalStack), schema
make reference-data      # ~760 MB: mangrove rasters, OSM extract
make layers              # boundaries, mangroves, settlements (~15 min, one-off)
make run                 # fetch NOSDRA, validate, analyse (~1.5-2.5 min)
make api                 # GraphiQL at http://localhost:8000/graphql
make web                 # map at http://localhost:5173
```

Try in GraphiQL:

```graphql
{
  explainSpill(id: "281734") {
    steps { step outcome }
    spill { issues { code severity message } }
    rawRecord
  }
  operators(minReports: 150) { operator reports shareUnplaceable shareMissingQuantity }
}
```

## Tests

`make check` runs ruff, mypy (strict) and pytest. Unit tests cover the
record-level parsing; integration tests run the full ingest→validate path
against a throwaway PostGIS container with a small synthetic geography,
including the edge cases from [DECISIONS.md](docs/DECISIONS.md).

## Deploying

`infra/` provisions the API as a Fargate service behind an ALB, the pipeline
as a weekly scheduled Fargate task, RDS Postgres (PostGIS) with an
RDS-managed secret, a versioned S3 bucket for raw snapshots, and a CloudWatch
alarm on the pipeline's `run.failed` log events. `terraform output
run_migrations` prints the one-off migration command.

## Docs

- [FINDINGS.md](docs/FINDINGS.md): what the data shows, and its limits
- [DECISIONS.md](docs/DECISIONS.md): choices and the reasons for them
- [DATA_SOURCES.md](docs/DATA_SOURCES.md): sources, licences, checks
- [PERFORMANCE.md](docs/PERFORMANCE.md): where time goes and what was done about it
- [TESTING.md](docs/TESTING.md): how to test and verify everything, step by step

## Data and licences

NOSDRA Oil Spill Monitor; OCHA COD-AB (CC BY-IGO); Global Mangrove Watch
v3.0 (CC BY 4.0); OpenStreetMap contributors (ODbL). Data analysis window:
2005–2024.
