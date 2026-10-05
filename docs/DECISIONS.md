# Decisions

The choices that weren't obvious, and why I made them.

## Keeping the original data

Every download of the register is saved exactly as published, and never
changed. The checked version is rebuilt from it each time, all at once, so
nobody ever sees a half-finished result. If the checks change, the old
results can be rebuilt from the saved download.

Reports with serious problems are kept and marked as unusable, not deleted.
Otherwise the figures on how much of the register is usable would be wrong.

Reports dated before 2005 are left out. Reports with a missing or impossible
date, like 1902 or a date in the future, are kept and marked, so they still
count in the quality figures.

Local government area is the smallest area used, because the official ward
boundaries only cover three states in the north-east.

## Fixing locations

Some reports have locations in the wrong format. The code doesn't guess
which fix is right. It works out every way the numbers could be read (as
written, with latitude and longitude swapped, as Nigerian grid coordinates,
with the decimal point moved, or as degrees-minutes-seconds) and then checks
each one on the map.

A fix is only kept if it agrees with the report. It has to land in the state
the report names, or near the local government area it names if there's no
state. The first version just took any reading that landed on land, and put
a Rivers spill in Oyo, 500 km away. Now a report that can't be fixed safely
is left without a location instead of being put somewhere wrong.

Agreeing with the report doesn't prove a fix is right. Before the code could
read degrees-minutes-seconds, one such report was "fixed" into Degema. That
was the right state but the wrong place. It now lands in Ahoada West, which
is the area the report names.

If a report gives a state, the state counts more than the area name, because
the same name can appear in different states. There's a Kaiama in Kwara and
another in Bayelsa.

Nigeria's grid has three zones (west, middle and east). The same numbers give
slightly different places in each zone, 4 to 9 km apart, which is enough to
change the local government area. Each zone is meant for one part of the
country, so that decides between readings that both agree with the report,
but nothing more. When the zone counted for more than the state, some Abia
reports landed in Rivers: the company had used east-zone coordinates for a
site in the middle zone.

One bug was easy to miss. When sorting candidates from best to worst,
Postgres puts empty values first. A check against a missing state came out
empty instead of false, which pushed a wrong candidate to the top. Every
check now turns an empty result into false.

Spills at sea are allowed outside every state, but only off Nigeria's coast.
Without a limit on longitude, points on land in Cameroon passed as offshore.

## Matching area names

Reports spell local government areas in many ways: "UKWA-WEST", "Ukwa West
LGA", "Deyema" for Degema. A standard text-similarity score got this wrong. It
rated "Ukwa West" and "Saki West" as more alike than "Deyema" and "Degema",
because of the shared word "West". So the matcher ignores words like North,
South, East, West and "LGA", and treats two names with different directions
(Ukwa West and Ukwa East) as different places. Short forms like ONELGA (for
Ogba/Egbema/Ndoni) still don't match.

## Limits

All the limits are in [rules/v1.yaml](../rules/v1.yaml). Changing one should
mean a new version of that file.

| Limit | Value | Why |
|---|---|---|
| Duplicates | Same company, within 250 m and 3 days | Same pipeline, same incident. 367 of the pairs it finds also share an incident number. |
| Largest believable spill | 50,000 barrels | The biggest spill of the period, Bonga in 2011, was about 40,000 barrels |
| State borders | 1 km leeway | GPS and boundaries aren't exact. This removed about 200 false alarms. |
| Area borders | 2 km leeway | Area boundaries are less exact than state ones |
| Shared coordinates | 5 or more reports | Fewer than that can be the same leak point |

A quantity written as "NIL" is treated as unreadable, not as zero, because
it could mean nothing leaked or nothing was measured.

## The analysis

The analysis measures what was near a spill, not how much damage it did.
Mangrove within 1 km is what was at risk.

It used to measure mangrove within 5 km too. That took over 90% of the
running time and added little, because the area summaries already give the
wider picture, so it was dropped.

Spills before 2014 are compared with the 2007 mangrove map, and later ones
with the 2020 map.

## Tools

The mangrove and settlement data are loaded with a separate GDAL container,
so the main app doesn't need GDAL installed. A Python step then cleans the
loaded data and records where each layer came from.

Dependencies are locked to versions from a fixed date, so installs are the
same every time.
