# Weaknesses

What isn't right yet, and what I'd do about each one. The limits of the data
itself are covered in [FINDINGS.md](FINDINGS.md#limits).

## The checks

**The rules file isn't really versioned.** Each checked report records that
it used "v1" of [rules/v1.yaml](../rules/v1.yaml), but nothing stops someone
editing that file in place, and there's no way to run two versions side by
side. To fix it, I'd make a change to the rules mean a new file, and add a
command that runs both versions on the same download and lists the reports
whose result changes.

**Some limits are written into the code instead of the rules file.** The 1 km
radius for mangroves, the 2 km radius for settlements, the 2014 cut-off
between the two mangrove maps, the 2 km leeway at area borders and the 5 km
used to place spills just off the coast are all in the SQL. They should move
into the rules file with the others.

**Short forms of area names don't match.** Reports often write "ONELGA" for
Ogba/Egbema/Ndoni, and the name matcher can't connect the two. A small table
of known short forms would fix it.

**Some reports that are clearly in the wrong place only get a warning.** Two
reports from the Qua Iboe oil terminal at Ibeno say they happened on land,
but their coordinates are about 60 km east, near the Bakassi peninsula. They
get a warning because the location doesn't match the habitat, but they are
still used. A report that says "land" and is more than a few kilometres from
any Nigerian land should probably be left out instead.

**Every report is checked again whenever the register changes.** A download
that hasn't changed is skipped, but if even one report changes, all 21,000
are checked again. That's because some checks, like finding duplicates,
compare reports with each other. It takes about 20 seconds, which is fine
now. With much more data, I'd check only the reports that changed and the
reports near them.

**Each changed download is stored in full.** The original data is kept so
any result can be traced back, but that means another 21,000 rows every time
the register changes. Storing only the reports that are new or different
would keep the same history in far less space.

**The analysis period ends on the day it runs.** Reports are analysed from
2005 up to today, so running it on a different day can include slightly
different reports. Each run should record the period it used.

## The code

**One file does too much.** `src/sheen/api/schema.py` holds the GraphQL types,
the queries and the logic that writes the `explainSpill` steps. The trends
query sits in `app.py` instead of with the other queries. Both would be
easier to follow split into smaller files.

**The map loads every spill at once.** That's about 14,000 points and 3 MB
every time the page opens. Loading only what's on screen, or serving the
points as map tiles, would make it much lighter.

**The tests use a small made-up map.** They prove each rule works, but not
that every real report is handled correctly. I'd add a handful of real
reports as test cases, like 281734 (degrees-minutes-seconds) and the Bodo
spills (no coordinates).

**The API has no login or limits.** That's fine on a laptop, but it isn't
ready to put online as it is.
