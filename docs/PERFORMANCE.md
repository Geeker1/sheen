# Performance

Timings on a laptop (8 cores, PostGIS 16 in Docker) with the full register
(about 21,000 records):

| Stage | Time |
|---|---:|
| Ingest 21k records | about 1.5 s (plus the download) |
| Validate | about 17 s |
| Analyse | about 17 s |

Each stage logs per-step timings and stores them in
`ops.pipeline_runs.details.step_seconds`.

## Mangrove exposure: 430 s to 16 s

The first version measured mangrove area within 1 km and 5 km of each spill
and took 430 s. On a 500-point sample, a 1 km radius touched 20 mangrove
polygons per point and 5 km touched 264; the 5 km part took 33 ms per point
against 3 ms, over 90% of the time.

What changed:

1. Dropped the 5 km radius. The per-LGA mangrove totals cover the wider
   picture.
2. Built each buffer once per point in a `LATERAL` subquery. Inside the
   aggregate, `ST_Buffer` ran once per spill and polygon pair.
3. Skipped `ST_Intersection` for polygons wholly inside the disc
   (`ST_CoveredBy`, then plain `ST_Area`).
4. Computed per distinct point, since many reports share coordinates.

That brought it to 61 s. The rest came from planner statistics. Validation
ran `ANALYZE` straight after the bulk load, before the spatial steps set
`analysable`, so Postgres believed almost no rows were analysable and chose a
nested-loop plan. Analysing again after the last update brought the step to
16 s. Before that fix was in place, the same stale statistics briefly made
the step take over 6 minutes.

Mangrove polygons are cut into pieces of at most 256 vertices when loaded
(`ST_Subdivide`), which keeps GiST lookups selective.

## LGA summary: 71 s to 0.1 s

Mangrove area per LGA was recomputed on every run, though it only changes
when the layers do. It now has its own materialised view
(`ref.lga_mangroves`), refreshed by `sheen ingest layers`.

## Loading layers

Promoting the polygonised mangroves used to run `ST_MakeValid` on every
polygon and took about 9 minutes. It now only repairs polygons that fail
`ST_IsValid`. This is a one-off load, not part of the weekly run.

## If it needed to go further

- Aggregate mangrove pixels into a 100 m grid of hectares per cell, so
  exposure becomes a sum over nearby points.
- Run exposure per state in parallel.
- Serve map points as vector tiles (`ST_AsMVT`) instead of 3 MB of GeoJSON.
