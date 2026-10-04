# Decisions

Choices that weren't obvious, and why they were made.

## Data model

Raw snapshots are append-only. Each one is stored as published in
`raw.spill_reports`, archived to S3, and hashed. `clean.*` holds only the
latest validation and is rebuilt in a single transaction, so readers never
see a half-finished table. Any older result can be rebuilt from raw plus the
ruleset version stored on each row. If people needed to query old validations
directly, clean rows would have to be keyed by run instead.

Records with errors stay in `clean.spills` with `analysable = false` rather
than being deleted, otherwise the data-quality figures would be wrong.

Records outside the 2005-2024 window are dropped from clean, but only if their
date is valid. Missing or implausible dates (such as 1902) stay in so they
count towards the quality figures.

LGA is the finest admin level used, because the OCHA ward layer only covers
Borno, Adamawa and Yobe.

## Coordinate corrections

The Python pass doesn't choose a fix. It produces every plausible reading:
as published, swapped, five projected CRSs in both axis orders, decimal
shifts and packed DMS. PostGIS then checks each one against real boundaries.

A corrected reading is only accepted if the report supports it: it must land
in the reported state, or near an LGA matching the reported LGA name when no
state is given. The first version took whichever reading landed on land and
put a Rivers spill in Oyo, 500 km away. A record that can't be corroborated is
marked `COORD_UNRESOLVED` instead of being placed somewhere confidently wrong.

Corroboration isn't proof. Before DMS parsing existed, `0509146, 0063452.0`
was reprojected into Degema, which is in the right state but the wrong place.
It is now read as DMS and lands in Ahoada West, the LGA the report names.

When a state is reported, it outranks the LGA name. Names repeat across
states (there is a Kaiama in Kwara and one in Bayelsa).

The projection zone only breaks ties. Nigeria's three Minna belts are set up
so the same grid values land close together in each belt, but 4 to 9 km
apart, which is enough to change the LGA. The reading that falls inside its
own belt's longitude band wins among corroborated readings. Ranking zone above
state got the Ukwa West (Abia) records wrong: the operator had used East Belt
coordinates for a site in the Mid Belt band.

The ranking flags are wrapped in `coalesce(..., false)`. Postgres sorts NULLs
first in a descending sort, and a comparison against a missing state was NULL,
which put the wrong candidate on top.

Offshore readings must also lie between 2.7E and 8.6E, Nigeria's coastline.
Without that, "within 250 km of Nigeria and south of 6.5N" matched land in
Cameroon.

## LGA name matching

Plain trigram similarity scored "Ukwa West" against "Saki West" at 0.33 and
"Ahoada West" against "Ahoada East" at 0.50, both higher than the real typo
"Deyema" against "Degema" (0.40). `ref.lga_name_similarity` compares names
with compass words and "LGA" removed, and returns 0 when both names have
compass words that differ. The threshold is 0.4. Acronyms such as ONELGA
(Ogba/Egbema/Ndoni) still don't match; that needs an alias table.

## Thresholds

All in [rules/v1.yaml](../rules/v1.yaml). Changing one means a new ruleset
version.

| Setting | Value | Reason |
|---|---|---|
| Duplicate radius and window | 250 m, 3 days | Same pipeline segment, same incident. 367 flagged pairs also share an incident number. |
| Largest plausible quantity | 50,000 bbl | Bonga (2011), the biggest spill of the period, was about 40,000 bbl |
| State border tolerance | 1 km | GPS and boundary precision. Cut state mismatches from 662 to 466. |
| LGA border tolerance | 2 km | LGA boundaries are less precise than state ones |
| Reused coordinate | 5 or more incidents | Fewer repeats can be the same leak point |

A quantity of "NIL" is treated as unparseable, not zero, because it could
mean nothing spilled or nothing measured.

## Analysis

Exposure is proximity, not damage. Mangrove area within 1 km says what was at
risk.

A 5 km radius was dropped: it touched 13 times as many polygons as 1 km and
took over 90% of the runtime, and the per-LGA figures already give the wider
picture. See [PERFORMANCE.md](PERFORMANCE.md).

Incidents before 2014 use the 2007 mangrove extent; later ones use 2020.

## Infrastructure

The Fargate tasks run in public subnets with public IPs and no NAT gateway,
because a NAT gateway would cost more than everything else combined. Security
groups only allow inbound traffic from the load balancer, and the database is
in private subnets. With sensitive data or a bigger budget, the tasks would
move to private subnets behind NAT or VPC endpoints.

Reference layers are loaded with the GDAL container, not the app, which keeps
GDAL out of the application image. A Python step then promotes the staged
data and records its source in `ref.sources`.

Dependency lockfiles are resolved as of the end of the data window
(`exclude-newer` for uv, `--before` for npm), so the environment matches the
snapshot.
