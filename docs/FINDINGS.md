# Findings

These figures cover reports from 1 January 2005 up to the latest download.
The most recent usable report is from September 2026. NOSDRA updates the
register from time to time, so the numbers shift a little.

A note on causes. The cause of each spill is decided at a site visit led by
the oil company, with regulators and community members present. Communities
have long disputed many of the sabotage findings. The numbers below are what
the register says, not a judgement on what really caused each spill.

## A third of the register can't be mapped

NOSDRA published 21,171 reports. 26 are from before 2005, which leaves
21,145. Of those, 13,884 (66%) can be used. The rest can't, mostly for these
reasons:

| Reason | Reports | Share |
|---|---:|---:|
| No usable location | 4,722 | 22% |
| The report says there was no spill | 1,921 | 9% |
| NOSDRA marked it invalid | 693 | 3% |

Some reports have more than one of these problems, so the numbers overlap.

Almost a quarter of reports have no coordinates at all, and 38% don't say
how much oil spilled. So the total of 718,000 barrels is the least that was
reported, not an estimate of what actually spilled. And anyone who simply
counts the rows will overcount spills by about 9%, because of the reports
that say there was no spill.

## Locations come in several formats

| Format | Example | Fixed |
|---|---|---:|
| Nigerian grid coordinates | `505315.78, 61913.044` | 35 |
| Degrees-minutes-seconds with no spaces | `04505482, 006281269` | 5 |
| Decimal point in the wrong place | `50.4926111, 5.9171944` | 2 |
| Couldn't be fixed | `495259733, 685983183` | 17 |

A fix is only kept when it lands in the state the report names (see
[DECISIONS.md](DECISIONS.md#fixing-locations)). The area name isn't part of
that check, which makes it a fair test of the fixes: 28 of the 33 grid
reports that name an area land inside it, and the other 5 land right next to
it. All 3 degrees-minutes-seconds reports that name an area land inside it.

## Reports often contradict themselves

- 505 reports (2%) name a state that their own coordinates aren't in, even
  allowing 1 km of leeway at borders. Most are neighbouring states, like
  Rivers and Bayelsa, which makes sense for pipelines that cross state lines.
- 1,162 (6%) name a local government area that isn't where their
  coordinates are, or within 2 km of it.
- 337 share exactly the same coordinates with four or more other reports.
  That usually means someone entered a facility or a default location, not
  where the spill happened.
- 1,783 look like repeats of an earlier report: same company, within 250 m
  and 3 days. 367 of these pairs also share an incident number.

## Some companies leave out much more than others

Companies with at least 150 reports, not counting reports that say there was
no spill or that NOSDRA marked invalid:

| Company | Reports | No location | No quantity | No cause | No site visit date | Sabotage, where a cause is given |
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

MPN (Mobil) works offshore, where community site visits and pipeline
sabotage mostly don't happen. That explains its site visit and sabotage
columns, so it's fairer to compare the onshore companies with each other.

## Where and when

Rivers (5,394 usable reports), Bayelsa (4,204) and Delta (2,169) make up 85%
of the total. The busiest areas are Southern Ijaw (2,354), Ogba/Egbema/Ndoni
(1,825) and Ahoada West (1,063). Kaduna and Abuja show up because fuel
pipelines run north to the Kaduna refinery. On the map, you can see the
spills follow the pipelines.

The number of usable reports peaked at about 1,500 a year in 2013 and 2014,
fell to 486 in 2020, and rose again to 952 in 2023. 2025 has 392 and 2026
has 158 up to September, but recent years may still fill in as reports are
completed. These are counts of reports, and the way companies report has
changed over the years, so they aren't an exact count of spills. Click any
area on the map to see its numbers by year.

## Ogoni and the Bodo spills

593 reports can be placed in Ogoni's four areas (Eleme, Gokana, Khana and
Tai). 438 of them are usable: 182 in Eleme, 180 in Gokana, 73 in Tai and 3 in
Khana. Of the 155 that aren't, 138 say there was no spill, 9 are marked
invalid and 8 have no date. Usable reports rose to 43, 37 and 50 a year in
2012, 2013 and 2014, dropped back, then peaked again at 53 in 2023.

The Bodo spills show how much depends on what the companies report. Report
6371 is SPDC's spill on the Trans Niger Pipeline at Bodo on 28 August 2008.
It's recorded as 1,640 barrels, caused by equipment failure. An independent
assessment for Amnesty International put it at 103,000 to 311,000 barrels.
Neither that report nor the second Bodo spill, in December 2008 (report 6445,
2,200 barrels), has coordinates. So both are missing from any map made from
the register, and from Ogoni's 2008 figures here too.

## Spills and mangrove loss

I compared the 30 areas with more than 2,000 hectares of mangrove in 2007.
Areas with more spills didn't lose noticeably more mangrove between 2007 and
2020. Areas with more spills lost 1.7% of their mangrove, and areas with
fewer lost 1.3%, and the link between the two is very weak (a rank
correlation of 0.08).

That doesn't mean spills don't harm mangroves. The mangrove maps only show
whether mangrove is there, not how healthy it is, and oiled mangrove that's
still standing still counts as mangrove. Showing the damage would need
satellite measures of how healthy the trees are. Bonny is the exception: it
lost 10.3% of its mangrove. Finding out why, whether industry, dredging or
spills, would need a closer look on the ground.

## Limits

- The companies report their own spills, so the register can't show how many
  go unreported.
- OpenStreetMap is missing many villages in the Delta, so settlement counts
  are lower than the real numbers.
- Local government area is the smallest area the data allows.
- Sheen measures what was near a spill, not how much damage it did.
