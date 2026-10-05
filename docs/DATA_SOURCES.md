# Data sources

| Data | Where it comes from | Licence | Date |
|---|---|---|---|
| Spill reports | NOSDRA's Nigerian Oil Spill Monitor. Its public dashboard loads the data from `oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json`, and Sheen reads the same address. | Free to use, per NOSDRA | Reports from 2005 onwards |
| State and local government boundaries | OCHA's Nigeria boundaries on HDX (`cod-ab-nga`), version 1 | CC BY-IGO | 2019 |
| Mangroves | Global Mangrove Watch version 3.0 (Bunting et al. 2022), Zenodo record 6894273 | CC BY 4.0 | 2007 and 2020 |
| Settlements | Towns and villages from OpenStreetMap, using Geofabrik's file `nigeria-250101.osm.pbf` | ODbL 1.0 | 1 January 2025 |

Spill reports are loaded with `sheen ingest spills` and boundaries with
`sheen ingest boundaries`. Mangroves and settlements are loaded with
`scripts/load_reference_layers.sh`, then `sheen ingest layers`.

## The spill register

The register has 21,171 reports with 41 fields each. Many fields use short
codes, like `sab` for sabotage or `la` for land. The meanings come from the
legend in the Oil Spill Monitor's own website code (see
`db/migrations/versions/0002_seed_reference_codes.py`). Two codes, `gs` and
`mys`, appear in the data but not in the legend, so they're marked as
unknown. The same code can mean different things in different fields: `co`
is condensate when it describes what spilled, and coastland when it
describes where.

Each download is the whole register. Sheen stores a fingerprint (a SHA-256
hash) of every download, which makes it easy to tell when nothing has
changed.

## Checks

The mangrove maps were checked against Global Mangrove Watch's own figure.
Sheen counts 833,978 hectares of mangrove inside Nigeria's state boundaries
in 2020. Global Mangrove Watch gives 844,243 hectares for Nigeria, 1.2% more.
The difference is mangrove just off the coastline, outside the state
boundaries.

## Gaps

OpenStreetMap is missing many villages in the Delta (it has 5,392 places in
the area Sheen uses), so settlement counts are lower than the real numbers.
GRID3's settlement data would be better, but the files are 2 to 3 GB.
