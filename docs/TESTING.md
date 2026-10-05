# Testing Sheen

There are three ways to check that Sheen works, from quickest to most
thorough. Each one says what you should see.

## Before you start

You need:

- Docker
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which you
  can install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node 22, but only for the map

Then, in the project folder:

```bash
uv sync               # install the Python dependencies
cp .env.example .env  # local settings
```

## 1. The automated tests (about a minute)

```bash
make check
```

This checks the code style, checks the types, and runs the tests. At the end
you should see `75 passed`.

Some tests start their own throwaway PostGIS database in Docker, so Docker
needs to be running. You don't need to start anything else.

| Test file | What it checks | Needs Docker |
|---|---|---|
| `tests/test_normalize.py` (49 tests) | Reading each field of a report: dates, quantities, causes, state names, and every coordinate format | No |
| `tests/test_pipeline_db.py` (13 tests) | The full check on a small made-up map: fixing locations, rejecting fixes that don't match the report, mismatches, duplicates, and the area name matcher | Yes |
| `tests/test_api.py` (13 tests) | The API: queries, filters, paging, `explainSpill`, the map data and the trends endpoint | Yes |

A few useful variations:

```bash
uv run pytest tests/test_normalize.py   # just the tests that don't need Docker
uv run pytest -k duplicate -v           # just the tests about duplicates
```

The GitHub checks also build the Docker image and the map:

```bash
docker build -t sheen:local .
cd web && npm ci && npm run build
```

## 2. Run it on the real data (20 to 30 minutes)

This downloads about 760 MB the first time.

```bash
make up migrate       # start the database and a local S3, create the tables
make reference-data   # download the mangrove and OpenStreetMap files
make layers           # load boundaries, mangroves and settlements (about 15 minutes)
make run              # download the register, check it and analyse it (about a minute)
```

At the end of `make run` you'll see a line for each of the three stages. They
should say roughly this:

```
stage=ingest    rows_in=21171 rows_out=21171
stage=validate  rows_in=21171 rows_out=21145  out_of_window=26  analysable=13884
stage=analyse   rows_out=13884
```

NOSDRA updates the register from time to time, so your numbers may be a
little different.

### Look at the results in the database

```bash
docker compose exec db psql -U sheen -d sheen
```

```sql
-- The latest runs: did they work, how many rows, how long they took
SELECT stage, status, rows_in, rows_out, round(extract(epoch FROM finished_at - started_at)) AS secs
FROM ops.pipeline_runs ORDER BY started_at DESC LIMIT 6;

-- The most common problems (missing quantity and missing coordinates come top)
SELECT code, severity, count(*) FROM clean.spill_issues GROUP BY 1, 2 ORDER BY 3 DESC;

-- Locations that were fixed: what was published, and where it ended up
SELECT s.spill_id, s.lga_reported, a.name AS located_in, i.message
FROM clean.spill_issues i
JOIN clean.spills s USING (spill_id)
LEFT JOIN ref.admin_areas a ON a.pcode = s.lga_pcode
WHERE i.code IN ('COORD_REPROJECTED', 'COORD_DMS_PARSED', 'COORD_DECIMAL_SHIFTED');

-- How often each company leaves things out
SELECT operator, reports, share_unplaceable, share_missing_quantity
FROM analysis.operator_quality WHERE reports >= 150 ORDER BY reports DESC;

-- The area name matcher
SELECT ref.lga_name_similarity('Ukwa West', 'Ukwa East'),  -- 0: different places
       ref.lga_name_similarity('DEYEMA', 'Degema');        -- 0.4: a typo, so it matches
```

### Reports worth looking at

Each of these shows one part of the checking at work. Look them up with
`explainSpill` (see below).

| Report | What happened |
|---|---|
| `281734` | Published as `04505482, 006281269`. Read as degrees-minutes-seconds, it lands in Abua/Odual, which matches the site description. |
| `145909` | Grid coordinates and no state. Placed in Bonny, next to the Okrika it names, instead of in Oyo. |
| `279988` | Reported in Abia. Only the east-zone reading of its grid coordinates lands in Abia, so that one is used. |
| `190484` | Grid coordinates that land in Degema, as the report says. |
| `236565` | Published as `495259733, 685983183`. No reading fits, so it's left without a location instead of being guessed. |

## 3. The API and the map

```bash
make api   # http://localhost:8000/graphql
make web   # http://localhost:5173, in a second terminal
```

Some queries to paste into the explorer at http://localhost:8000/graphql:

```graphql
# The full history of one report
{
  explainSpill(id: "281734") {
    steps { step outcome }
    spill { issues { code severity message } }
    rawRecord
  }
}
```

```graphql
# Reports whose grid coordinates were converted, five at a time
# (run it again with after: "<endCursor>" for the next five)
{
  spills(filter: { issueCode: "COORD_REPROJECTED" }, first: 5) {
    totalCount hasNextPage endCursor
    items { id operator incidentDate locationMethod lga { name stateName } }
  }
}
```

```graphql
# Summaries
{
  summary { reportsInWindow analysable reportedBbl }
  lgas(stateCode: "RI", limit: 5) { name spills reportedBbl mangroveHa2020 mangroveChangePct }
  issueTypes { code severity count }
  pipelineRuns(limit: 3) { stage status rowsOut details }
}
```

You can also open these in a browser:

```
http://localhost:8000/trends?lga=Gokana,Khana,Tai,Eleme   spills per year in Ogoni
http://localhost:8000/trends?state=RI&by=month            Rivers, month by month
http://localhost:8000/healthz                             should say {"status":"ok"}
http://localhost:8000/docs                                every endpoint, with a form to try them
```

On the map you should see:

- Areas shaded by number of spills, darkest in Southern Ijaw, with a colour
  key in the side panel
- Spill points following the pipelines. Hollow points are locations that
  were fixed.
- The "Mangrove change" option recolouring the areas, with its own key
- Clicking a spill shows what happened to its report
- Clicking an area outlines it and shows its spills per year. Hover over a
  bar for the numbers; "Show all" goes back to every area.

## If something goes wrong

| Problem | What to do |
|---|---|
| `connection refused` on port 5433 | Run `make up` and wait until `docker compose ps` shows the database as healthy |
| The first `make migrate` fails | The database restarts once when it's first created. Run `make migrate` again. |
| `No successful ingest` | Run `make run`, or `sheen ingest spills`, before `sheen validate` |
| The Docker tests are skipped | Docker isn't running |
| The map is empty | Start the API with `make api` |
| An `archive.failed` warning | The local S3 isn't running (`docker compose up -d s3`). The download is still saved in the database, so nothing is lost. |
