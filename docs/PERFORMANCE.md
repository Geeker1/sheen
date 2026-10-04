# Performance notes

Timings on a laptop (8 cores, PostGIS 16 in Docker), full 2005–2024 data.

| Stage | Time |
|---|---:|
| Ingest 21k records (`COPY`) | 1.4 s |
| Validate (record checks + 12 spatial steps) | ~14 s |
| Analyse | ~65 s |

Every stage logs per-step timings (`validate.step`, `analyse.step`) and
stores them in `ops.pipeline_runs.details.step_seconds`, so regressions
show up in the data.

## Mangrove exposure: 430 s → 61 s

The first version computed mangrove area within 1 km and 5 km of each
spill and took 430 s.

1. **Measured instead of guessing.** On a 500-point sample, a 1 km radius
   touched 20 mangrove polygons per point on average and a 5 km radius 264.
   The 5 km query took 33 ms/point vs 3 ms/point: over 90% of the cost.
2. **Dropped the 5 km radius.** Per-LGA mangrove totals already cover
   wider context.
3. **Buffer once per point, not once per joined row.** `ST_Buffer` inside
   the aggregate was evaluated for every (spill, polygon) pair; it now
   lives in a `LATERAL` subquery.
4. **Skip intersections when a polygon is wholly inside the disc**
   (`ST_CoveredBy` → plain `ST_Area`).
5. **Compute per distinct point.** Many reports share coordinates
   (13.3k spills → 12.1k distinct point/year pairs).

Polygons are subdivided to ≤256 vertices on load (`ST_Subdivide`), so
GiST index lookups return small, tight geometries.

## LGA summary: 71 s → 0.4 s

Per-LGA mangrove area was recomputed on every run, although it only changes
when reference layers change. It moved into its own materialised view
(`ref.lga_mangroves`), refreshed by `sheen ingest layers`.

## Layer promotion: known slow spot

Promoting the polygonised mangroves originally ran `ST_MakeValid` on every
polygon (~9 min). It now only repairs polygons that fail `ST_IsValid`. This
is a one-off load, not part of the scheduled pipeline.

## Next steps, if needed

- Pre-aggregate mangrove pixels to a 100 m grid of hectares per cell. Then
  exposure is a point-in-radius sum over an indexed point table.
- Run the exposure query per state in parallel workers.
- Serve map points as vector tiles (`ST_AsMVT`) instead of 3 MB GeoJSON.
