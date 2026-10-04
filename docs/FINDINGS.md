# Findings

What the NOSDRA spill register shows once it has been validated. Window:
incidents dated 2005-01-01 to 2024-12-31. All figures are reproducible with
`make run` against the snapshot described in [DATA_SOURCES.md](DATA_SOURCES.md).

> **On "sabotage".** Causes in the register are recorded after a Joint
> Investigation Visit (JIV) led by the operator, with regulators and
> communities attending. Communities have long disputed many sabotage
> findings. The figures below report what the register says, not what caused
> each spill.

## 1. A third of the register can't be used for spatial analysis

| | Reports | Share |
|---|---:|---:|
| Published by NOSDRA (all dates) | 21,171 | |
| Outside the 2005–2024 window | 728 | |
| **In window** | **20,443** | 100% |
| Usable for analysis | 13,334 | **65.2%** |
| No usable location | 4,714 | 23.1% |
| Recorded as "no spill" (contaminant = `no`) | 1,791 | 8.8% |
| Marked invalid by NOSDRA | 675 | 3.3% |

The biggest single gap is location: **22.7% of reports have no coordinates
at all.** After that comes volume: **38% have no estimated quantity**, so
any total volume (693,000 bbl across usable reports) is a floor, not an
estimate.

About 9% of records in a "spill" register are explicitly *not* spills. Any
analysis that counts rows without reading the `contaminant` code overstates
spill numbers by that much.

## 2. Coordinates arrive in at least four formats

Most coordinates are decimal degrees, but some are not. Instead of throwing
those away, the validator proposes possible interpretations and keeps one
only if the report itself backs it up (see [DECISIONS.md](DECISIONS.md#coordinate-corrections)).

| Format found | Example (as published) | Recovered |
|---|---|---:|
| Nigerian grid metres (Minna belts / UTM) | `505315.78, 61913.044` | 33 |
| Packed degrees-minutes-seconds | `04505482, 006281269` → 4°50′54.82″N 6°28′12.69″E | 5 |
| Misplaced decimal point | `50.4926111, 5.9171944` → 5.049…N | 2 |
| Unrecoverable | `495259733, 685983183` | 15 |

All 40 recovered locations land in the reported state. Of the reprojections
that name an LGA, 27 of 32 land in that LGA and the other 5 in a neighbouring
one. All 3 DMS records that name an LGA land in it ("ONELGA" being the common
acronym for Ogba/Egbema/Ndoni). That is good independent evidence that the
parsing is right.

## 3. Reports often disagree with their own coordinates

- **466 reports (2.3%)** name a state the point is not in (with 1 km
  tolerance at state borders). Most pairs are neighbours (Rivers↔Bayelsa,
  Abia↔Rivers, Delta↔Edo), consistent with pipelines that cross state lines.
- **1,127 (5.5%)** name an LGA that is neither the one the point falls in
  nor within 2 km of it.
- **328** share an exact coordinate with at least four other incidents,
  which usually means a facility or default location was entered rather
  than the spill site.
- **2,621 reports** look like duplicates: same operator, within 250 m and
  3 days of another report. 367 of these also share the incident number.

## 4. Reporting completeness varies a lot by operator

Operators with 150+ in-window reports (excluding "no spill"/invalid):

| Operator | Reports | No location | No quantity | No cause | No JIV date | Sabotage (of known cause) |
|---|---:|---:|---:|---:|---:|---:|
| NAOC | 7,942 | 14% | 34% | 6% | 14% | 84% |
| SPDC | 4,747 | 30% | 39% | 18% | 18% | 83% |
| MPN | 1,570 | 56% | 10% | 13% | 100% | 0.2% |
| PPMC | 901 | 31% | 70% | 16% | 18% | 81% |
| Chevron | 812 | 65% | 16% | 13% | 64% | 28% |
| NPDC | 407 | 9% | 13% | 1% | 1% | 77% |
| Heritage | 256 | 0% | 7% | 0% | 0% | 41% |
| Seplat | 227 | 5% | 23% | 3% | 3% | 38% |

Read with care: MPN (Mobil) operates offshore, where community JIVs and
pipeline sabotage largely don't apply. Its missing JIV dates and near-zero
sabotage share come from where it operates, not from how well it reports.
Comparisons are fair among onshore operators.

## 5. Where spills happen

Rivers (5,200 usable reports), Bayelsa (4,064) and Delta (2,036) account for
85%. The busiest LGAs are Southern Ijaw (2,305), Ogba/Egbema/Ndoni (1,780)
and Ahoada West (1,040). Kaduna (141) and the FCT appear because of the
product pipelines that run north to the Kaduna refinery.

Usable reports per year rise to a peak in 2013–2014 (≈1,500/yr), fall
through 2020 (486), and rise again to 950 in 2023. Changes in how actively
operators reported over these years are part of that pattern; the series
measures reports, not spills.

On the map, spill points visibly trace the pipeline network.

## 6. No detectable link between spill density and mangrove extent loss

Across the 30 LGAs with more than 2,000 ha of mangrove in 2007, spills per
100 km² of mangrove do not correlate with the change in mangrove extent
2007–2020 (Spearman ρ = 0.05). LGAs with more spills lost 1.7% of mangrove
extent; those with fewer lost 1.3%.

This is **not evidence that spills don't harm mangroves.** Global Mangrove
Watch maps whether mangrove is *present*, not its condition. Oiled mangrove
that is still standing is still "mangrove". Detecting degradation needs
condition indices (e.g. NDVI time series), which is the natural next step.
Bonny is the outlier, losing 10.3% of its mangrove extent; causes there
(industrial expansion, dredging, spills) would need site-level work.

## Limitations

- The register is self-reported by operators and published by the
  regulator. Under-reporting can't be measured from the register itself.
- Settlement counts use OpenStreetMap, whose village coverage in the Delta
  is incomplete, so "settlements within 2 km" is a lower bound.
- LGA is the finest admin level available (the OCHA ward layer only covers
  three north-eastern states).
- Exposure measures proximity, not damage.
