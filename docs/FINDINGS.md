# Findings

Incidents dated 2005-01-01 to 2024-12-31, from the snapshot described in
[DATA_SOURCES.md](DATA_SOURCES.md).

A note on causes: they come from Joint Investigation Visits, which operators
lead with regulators and community members present. Communities have long
disputed many sabotage findings. The numbers below are what the register
says, not a judgement of what caused each spill.

## A third of the register can't be mapped

NOSDRA published 21,171 records. 728 fall outside the window, leaving 20,443.
Of those, 13,334 (65.2%) are usable for analysis. The rest:

| Reason | Reports | Share |
|---|---:|---:|
| No usable location | 4,714 | 23.1% |
| Recorded as "no spill" (contaminant `no`) | 1,791 | 8.8% |
| Marked invalid by NOSDRA | 675 | 3.3% |

These overlap, so they don't add up to the total. 22.7% of reports have no
coordinates at all, and 38% have no estimated quantity, so the reported total
of 693,000 bbl is a floor. Counting rows without checking the contaminant code
overstates spills by about 9%.

## Coordinates come in several formats

| Format | Published as | Recovered |
|---|---|---:|
| Nigerian grid metres (Minna belts, UTM) | `505315.78, 61913.044` | 33 |
| Packed degrees-minutes-seconds | `04505482, 006281269` (4 deg 50' 54.82" N, 6 deg 28' 12.69" E) | 5 |
| Misplaced decimal point | `50.4926111, 5.9171944` | 2 |
| Not recoverable | `495259733, 685983183` | 15 |

A correction is only kept when it lands in the state the report names (see
[DECISIONS.md](DECISIONS.md#coordinate-corrections)). Beyond that check, 27
of the 32 reprojected records that name an LGA land inside it and the other 5
in a neighbouring one; all 3 DMS records that name an LGA land in it. That is
independent evidence the parsing is right.

## Reports often disagree with their own coordinates

- 466 reports (2.3%) name a state the point isn't in, allowing 1 km at
  borders. Most are neighbouring pairs such as Rivers and Bayelsa, which fits
  pipelines crossing state lines.
- 1,127 (5.5%) name an LGA that is neither the one the point is in nor within
  2 km of it.
- 328 share an exact coordinate with four or more other incidents, which
  usually means a facility or default location was entered.
- 2,621 look like duplicates (same operator, within 250 m and 3 days); 367 of
  those also share an incident number.

## Reporting completeness varies by operator

Operators with at least 150 reports in the window, excluding "no spill" and
invalid records:

| Operator | Reports | No location | No quantity | No cause | No JIV date | Sabotage, of known causes |
|---|---:|---:|---:|---:|---:|---:|
| NAOC | 7,942 | 14% | 34% | 6% | 14% | 84% |
| SPDC | 4,747 | 30% | 39% | 18% | 18% | 83% |
| MPN | 1,570 | 56% | 10% | 13% | 100% | 0.2% |
| PPMC | 901 | 31% | 70% | 16% | 18% | 81% |
| Chevron | 812 | 65% | 16% | 13% | 64% | 28% |
| NPDC | 407 | 9% | 13% | 1% | 1% | 77% |
| Heritage | 256 | 0% | 7% | 0% | 0% | 41% |
| Seplat | 227 | 5% | 23% | 3% | 3% | 38% |

MPN (Mobil) operates offshore, where community JIVs and pipeline sabotage
mostly don't apply, so its JIV and sabotage columns reflect where it works,
not how it reports. Compare onshore operators with each other.

## Where and when

Rivers (5,200 usable reports), Bayelsa (4,064) and Delta (2,036) make up 85%.
The busiest LGAs are Southern Ijaw (2,305), Ogba/Egbema/Ndoni (1,780) and
Ahoada West (1,040). Kaduna (141) and the FCT appear because of the product
pipelines running north to the Kaduna refinery. On the map, spill points
trace the pipeline network.

Usable reports per year peak in 2013 and 2014 at about 1,500, fall to 486 in
2020 and climb back to 952 in 2023. This counts reports, and reporting
practice changed over the period, so it isn't a clean measure of spills.

## Ogoni and the Bodo spills

Ogoni's four LGAs (Eleme, Gokana, Khana and Tai) have 567 reports that can be
placed there. 420 are usable: Eleme 174, Gokana 174, Tai 71, Khana 1. Of the
147 that aren't, 131 are recorded as "no spill", 8 are marked invalid and 8
have no date.

The register shows how much depends on what operators report. Record 6371,
SPDC's spill on the Trans Niger Pipeline at Bodo on 28 August 2008, is
recorded as 1,640 barrels from equipment failure. An independent assessment
for Amnesty International estimated 103,000 to 311,000 barrels. Neither that
record nor the December 2008 Bodo spill (record 6445, 2,200 barrels) has
coordinates, so both are missing from any map made from the register.

## Spill density and mangrove loss

Across the 30 LGAs with more than 2,000 ha of mangrove in 2007, spills per
100 km2 of mangrove don't correlate with the change in mangrove extent from
2007 to 2020 (Spearman 0.05). LGAs with more spills lost 1.7% of their
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
