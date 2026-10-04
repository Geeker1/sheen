# Data sources

| Layer | Source | Licence | Describes | Loaded by |
|---|---|---|---|---|
| Spill reports | NOSDRA Nigerian Oil Spill Monitor, JSON endpoint behind the public dashboard (`oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json`) | Public; free to use per NOSDRA | Incidents; analysis uses 2005–2024 | `sheen ingest spills` |
| State & LGA boundaries | OCHA COD-AB Nigeria (`cod-ab-nga` on HDX), v01 | CC BY-IGO | Valid from 2019-04-17 | `sheen ingest boundaries` |
| Mangrove extent | Global Mangrove Watch v3.0 (Bunting et al. 2022), Zenodo record 6894273, 2007 and 2020 rasters | CC BY 4.0 | End of 2007 / end of 2020 | `scripts/load_reference_layers.sh` + `sheen ingest layers` |
| Settlements | OpenStreetMap `place=*` nodes, Geofabrik extract `nigeria-250101.osm.pbf` | ODbL 1.0 | OSM as of 2025-01-01 | same |

## Spill register

- 21,171 records, 41 fields. Codes (`sab`, `la`, `cr`, …) are decoded from
  the legend in the Oil Spill Monitor's own JavaScript bundle; see
  `db/migrations/versions/0002_seed_reference_codes.py`. `gs` and `mys`
  appear in the data but not in the legend and are labelled as unknown.
- The same code means different things in different fields: `co` is
  *condensate* as a contaminant and *coastland* as a habitat.
- The endpoint returns the full register on each call; snapshots are stored
  with their SHA-256 so unchanged data is easy to spot.

## Checks against published figures

- **Mangroves.** Polygonised GMW 2020 extent inside Nigeria's state
  boundaries: 833,978 ha. GMW's own country statistic for Nigeria 2020:
  844,243 ha (−1.2%). The gap is mangrove seaward of the admin coastline.

## Known gaps

- OSM settlement coverage in the Delta is incomplete (5,392 places in the
  extract's southern Nigeria window); counts are lower bounds.
- GRID3 settlement extents would be better but are 2–3 GB.
