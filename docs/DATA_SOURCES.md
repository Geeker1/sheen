# Data sources

| Layer | Source | Licence | As of |
|---|---|---|---|
| Spill reports | NOSDRA Nigerian Oil Spill Monitor, the JSON endpoint behind its public dashboard (`oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json`) | Public, free to use per NOSDRA | Analysis uses 2005-2024 |
| State and LGA boundaries | OCHA COD-AB Nigeria (`cod-ab-nga` on HDX), v01 | CC BY-IGO | Valid from 2019-04-17 |
| Mangrove extent | Global Mangrove Watch v3.0 (Bunting et al. 2022), Zenodo record 6894273, 2007 and 2020 rasters | CC BY 4.0 | End of 2007, end of 2020 |
| Settlements | OpenStreetMap `place=*` nodes from the Geofabrik extract `nigeria-250101.osm.pbf` | ODbL 1.0 | 2025-01-01 |

Spills are loaded with `sheen ingest spills`, boundaries with
`sheen ingest boundaries`, and mangroves and settlements with
`scripts/load_reference_layers.sh` followed by `sheen ingest layers`.

## The spill register

21,171 records with 41 fields. The codes (`sab`, `la`, `cr` and so on) are
decoded using the legend in the Oil Spill Monitor's own JavaScript; see
`db/migrations/versions/0002_seed_reference_codes.py`. `gs` and `mys` appear
in the data but not in the legend, so they're labelled unknown. The same code
can mean different things in different fields: `co` is condensate as a
contaminant and coastland as a habitat.

The endpoint returns the whole register on every call. Each snapshot is
stored with its SHA-256, which makes unchanged data easy to spot.

## Checks

Mangrove area: the polygonised 2020 extent inside Nigeria's state boundaries
comes to 833,978 ha. GMW's published figure for Nigeria in 2020 is 844,243 ha,
1.2% higher; the difference is mangrove just seaward of the admin coastline.

## Gaps

OpenStreetMap's settlement coverage in the Delta is thin (5,392 places in the
southern Nigeria window), so counts are a lower bound. GRID3 settlement
extents would be better but are 2 to 3 GB.
