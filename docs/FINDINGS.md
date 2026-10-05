# Findings

Incidents dated from 1 January 2005 to the latest snapshot (the most recent
usable report is from September 2026), from the source described in
[DATA_SOURCES.md](DATA_SOURCES.md). Figures change slightly as NOSDRA updates
the register.

A note on causes: they come from Joint Investigation Visits, which operators
lead with regulators and community members present. Communities have long
disputed many sabotage findings. The numbers below are what the register
says, not a judgement of what caused each spill.

## A third of the register can't be mapped

NOSDRA published 21,171 records. 26 are dated before 2005, leaving 21,145.
Of those, 13,884 (65.7%) are usable for analysis. The rest:

| Reason | Reports | Share |
|---|---:|---:|
| No usable location | 4,722 | 22.3% |
| Recorded as "no spill" (contaminant `no`) | 1,921 | 9.1% |
| Marked invalid by NOSDRA | 693 | 3.3% |

These overlap, so they don't add up to the total. 21.9% of reports have no
coordinates at all, and 37.9% have no estimated quantity, so the reported
total of 718,000 bbl is a floor. Counting rows without checking the
contaminant code overstates spills by about 9%.

## Coordinates come in several formats

| Format | Published as | Recovered |
|---|---|---:|
| Nigerian grid metres (Minna belts, UTM) | `505315.78, 61913.044` | 35 |
| Packed degrees-minutes-seconds | `04505482, 006281269` (4 deg 50' 54.82" N, 6 deg 28' 12.69" E) | 5 |
| Misplaced decimal point | `50.4926111, 5.9171944` | 2 |
| Not recoverable | `495259733, 685983183` | 17 |

A correction is only kept when it lands in the state the report names (see
[DECISIONS.md](DECISIONS.md#coordinate-corrections)). Beyond that check, 28
of the 33 reprojected records that name an LGA land inside it and the other 5
in a neighbouring one; all 3 DMS records that name an LGA land in it. That is
independent evidence the parsing is right.

## Reports often disagree with their own coordinates

- 505 reports (2.4%) name a state the point isn't in, allowing 1 km at
  borders. Most are neighbouring pairs such as Rivers and Bayelsa, which fits
  pipelines crossing state lines.
- 1,162 (5.5%) name an LGA that is neither the one the point is in nor within
  2 km of it.
- 337 share an exact coordinate with four or more other incidents, which
  usually means a facility or default location was entered.
- 1,783 look like duplicates of an earlier report (same operator, within
  250 m and 3 days); 367 of the matching pairs also share an incident number.

## Reporting completeness varies by operator

Operators with at least 150 reports, excluding "no spill" and invalid
records:

| Operator | Reports | No location | No quantity | No cause | No JIV date | Sabotage, of known causes |
|---|---:|---:|---:|---:|---:|---:|
| NAOC | 7,949 | 14% | 34% | 6% | 14% | 84% |
| SPDC | 4,765 | 30% | 39% | 18% | 18% | 83% |
| MPN | 1,602 | 55% | 10% | 13% | 100% | 0.4% |
| PPMC | 902 | 31% | 70% | 16% | 18% | 82% |
| Chevron | 826 | 64% | 16% | 13% | 63% | 28% |
| NPDC | 407 | 9% | 13% | 1% | 1% | 77% |
| Heritage | 290 | 0% | 7% | 0% | 0% | 39% |
| Seplat | 252 | 5% | 22% | 2% | 3% | 39% |
| Oando | 204 | 3% | 12% | 0% | 1% | 89% |

MPN (Mobil) operates offshore, where community JIVs and pipeline sabotage
mostly don't apply, so its JIV and sabotage columns reflect where it works,
not how it reports. Compare onshore operators with each other.

## Where and when

Rivers (5,394 usable reports), Bayelsa (4,204) and Delta (2,169) make up 85%.
The busiest LGAs are Southern Ijaw (2,354), Ogba/Egbema/Ndoni (1,825) and
Ahoada West (1,063). Kaduna and the FCT appear because of the product
pipelines running north to the Kaduna refinery. On the map, spill points
trace the pipeline network.

Usable reports per year peak in 2013 and 2014 at about 1,500, fall to 486 in
2020 and climb back to 952 in 2023. 2025 has 392 and 2026 (to September)
158; recent years may still fill in as reports are completed. This counts
reports, and reporting practice changed over the period, so it isn't a clean
measure of spills. The `/trends` endpoint gives this series for any LGA,
state or operator.

## Ogoni and the Bodo spills

Ogoni's four LGAs (Eleme, Gokana, Khana and Tai) have 593 reports that can be
placed there. 438 are usable: Eleme 182, Gokana 180, Tai 73, Khana 3. Of the
155 that aren't, 138 are recorded as "no spill", 9 are marked invalid and 8
have no date. Usable reports rise through 2012-2014 (43, 37 and 50 a year),
fall back, and peak again at 53 in 2023.

The register shows how much depends on what operators report. Record 6371,
SPDC's spill on the Trans Niger Pipeline at Bodo on 28 August 2008, is
recorded as 1,640 barrels from equipment failure. An independent assessment
for Amnesty International estimated 103,000 to 311,000 barrels. Neither that
record nor the December 2008 Bodo spill (record 6445, 2,200 barrels) has
coordinates, so both are missing from any map made from the register,
including the 2008 figure for Ogoni in the trend series.

## Spill density and mangrove loss

Across the 30 LGAs with more than 2,000 ha of mangrove in 2007, spills per
100 km2 of mangrove don't correlate with the change in mangrove extent from
2007 to 2020 (Spearman 0.08). LGAs with more spills lost 1.7% of their
mangrove; those with fewer lost 1.3%.

That doesn't show spills are harmless. Global Mangrove Watch records whether
mangrove is present, not its condition, and oiled mangrove that is still
standing counts as mangrove. Measuring damage would need a condition index
such as an NDVI time series. Bonny is the exception, losing 10.3% of its
extent; working out why (industry, dredging, spills) would need site-level
study.

## Limitations

- The register is self-reported by operators, so under-reporting can't be
  measured from it.
- OpenStreetMap's village coverage in the Delta is incomplete; settlement
  counts are a lower bound.
- LGA is the finest admin level available.
- Exposure is proximity, not measured damage.
