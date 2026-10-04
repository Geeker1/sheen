# Decisions

Short records of choices that weren't obvious, newest concerns first within
each section. Each says what was decided, why, and what would change it.

## Data model

**Raw is append-only; clean is replaced atomically.** Every snapshot is
stored untouched in `raw.spill_reports` (and archived to S3) with its
SHA-256. `clean.*` holds the latest validation, rebuilt in a single
transaction, so readers never see a half-validated table. Any earlier result
can be rebuilt from raw plus the ruleset version stored on each row.
*Would change if:* consumers needed to query historical validations
directly. Then clean rows would be keyed by run.

**Validation errors keep the record; they don't delete it.** A record with
an `error` issue stays in `clean.spills` with `analysable = false`. Data
quality statistics would be biased if failing records disappeared.

**Out-of-window records are dropped from clean, but only when well-dated.**
Records with missing or implausible dates (e.g. `1902`) stay in so they
count toward data-quality figures.

**LGA is the finest admin level.** The OCHA COD-AB ward layer only covers
Borno, Adamawa and Yobe.

## Coordinate corrections

**Python proposes, PostGIS decides.** The record-level pass doesn't guess a
single fix. It emits every plausible reading (as reported, swapped, five
grid CRSs × two axis orders, decimal shifts, packed DMS). PostGIS scores
each against real geography.

**A correction must be corroborated by the report.** A corrected point is
only accepted if it lands in the reported state or, when no state is given,
near an LGA matching the reported LGA name. Without this rule the first
version placed a Rivers spill in Oyo State, 500 km away, because one grid
reading happened to land on land. Uncorroborated records get
`COORD_UNRESOLVED` (an error) instead of a confident wrong location.

Corroboration is necessary but not sufficient. Before DMS parsing existed,
`0509146, 0063452.0` was "reprojected" into Degema. That was in the right
state but wrong, and it is now parsed as DMS into Ahoada West, the LGA the
report names.

**A reported state outranks an LGA name.** "Kaiama" exists in both Kwara
and Bayelsa, so a name match can't overrule a contradicting state.

**Projection zone breaks ties; it doesn't decide.** Nigeria's three Minna
belts share a near-continuous grid, so one easting/northing lands in roughly
the same place in each belt, but 4–9 km apart, enough to change the LGA.
Among corroborated readings, the one inside its own belt's longitude band
wins. Zone was originally ranked above state match, which got the Ukwa West
(Abia) records wrong: their operator recorded East-Belt coordinates while
working inside the Mid-Belt band.

**Every ranking flag is a real boolean.** In `ORDER BY … DESC`, Postgres
sorts NULLs first. A comparison against a missing state evaluated to NULL
and outranked TRUE until each flag was wrapped in `coalesce(…, false)`.

**Offshore is bounded by longitude too.** "Within 250 km of Nigeria, south
of 6.5°N" also matched Cameroon's land. Offshore candidates must lie between
2.7°E and 8.6°E (Nigeria's coastline).

## Name matching

**LGA names use a purpose-built similarity, not raw trigrams.** Plain
`pg_trgm` scored "Ukwa West" vs "Saki West" at 0.33 (shared word) and
"Ahoada West" vs "Ahoada East" at 0.50, higher than the real typo
"Deyema" vs "Degema" (0.40). `ref.lga_name_similarity` compares names with
compass words and "LGA" removed, and returns 0 when compass words conflict.
Threshold 0.4. *Known gap:* acronyms such as "ONELGA" (Ogba/Egbema/Ndoni)
need an alias table.

## Thresholds (rules/v1.yaml)

| Setting | Value | Why |
|---|---|---|
| Duplicate radius / window | 250 m / 3 days | Same pipeline segment and the same incident; 367 of the flagged pairs share an incident number, which supports the choice |
| Max plausible quantity | 50,000 bbl | Bonga (2011), the largest spill of the era, was ~40,000 bbl |
| State border tolerance | 1 km | GPS and boundary precision; cut state mismatches from 662 to 466 |
| LGA border tolerance | 2 km | Same reasoning; LGA boundaries are less precise than state ones |
| Reused coordinate | ≥ 5 incidents | Below that, repeats are plausibly the same leak point |

**"NIL" quantities are unparseable, not zero.** "NIL" could mean nothing
spilled or nothing measured. Treating it as 0 would bias totals downward.

## Analysis

**Exposure is proximity, not damage.** "Mangrove within 1 km" says what was
at risk.

**The 5 km radius was dropped.** It touched 13× more polygons than 1 km and
took over 90% of the stage's runtime. Wider context is already in the
per-LGA mangrove figures. See [PERFORMANCE.md](PERFORMANCE.md).

**Mangrove year follows the incident.** Incidents before 2014 use the 2007
GMW extent, later ones 2020.

## Infrastructure

**Fargate tasks in public subnets, no NAT gateway.** A NAT gateway would cost
more than the rest of the stack. Tasks get a public IP for outbound calls
(ECR, NOSDRA), and security groups only allow inbound traffic from the load
balancer. The database is in private subnets. *Would change if:* the API
handled sensitive data, or a VPC endpoint/NAT budget existed.

**Reference layers are loaded by a GDAL container, not the app.** Rasters
and the OSM extract are one-off loads; keeping GDAL out of the application
image keeps it small. A Python step then validates the staged data and
records where each layer came from in `ref.sources`.

**Dependencies are resolved as of the end of the data window.**
`exclude-newer` (uv) and `--before` (npm) pin the lockfiles to packages
published before 2025, so the environment matches the snapshot.
