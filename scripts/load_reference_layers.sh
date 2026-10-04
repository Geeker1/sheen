#!/usr/bin/env bash
# Polygonise / extract reference layers into the `stage` schema with GDAL.
#
# Runs inside the GDAL container so the Python app doesn't need GDAL:
#   docker compose run --rm gdal /work/scripts/load_reference_layers.sh
# then promote into `ref` with:
#   sheen ingest layers
#
# Inputs (downloaded by `make reference-data`):
#   data/raw/gmw/gmw_v3_{2007,2020}_gtiff.zip   Global Mangrove Watch v3.0
#   data/raw/osm/nigeria-250101.osm.pbf         OSM Nigeria as of 2025-01-01
set -euo pipefail

PG="PG:host=${PGHOST:-db} dbname=sheen user=sheen password=sheen"
RAW=/work/data/raw
WORK=/work/data/work
mkdir -p "$WORK"

# GMW tiles are named by their north-west corner. These cover the coastal
# Niger Delta from Lagos to the Cameroon border (3-8N, 2-10E).
TILE_GLOB='GMW_N0[3-8]E00[2-9]_*.tif'

for year in 2007 2020; do
    echo "== mangroves $year"
    zip="$RAW/gmw/gmw_v3_${year}_gtiff.zip"
    dir="$WORK/gmw_$year"
    rm -rf "$dir" && mkdir -p "$dir"
    # Read tiles straight out of the zip via GDAL's /vsizip/; nothing is extracted.
    python3 -c "import fnmatch, sys, zipfile
names = zipfile.ZipFile(sys.argv[1]).namelist()
print('\n'.join('/vsizip/' + sys.argv[1] + '/' + n for n in names if fnmatch.fnmatch(n.split('/')[-1], sys.argv[2])))" \
        "$zip" "$TILE_GLOB" > "$dir/tiles.txt"
    echo "   $(wc -l < "$dir/tiles.txt") tiles"

    # 0 = not mangrove; treat it as nodata so only mangrove pixels polygonise.
    gdalbuildvrt -q -srcnodata 0 -vrtnodata 0 -input_file_list "$dir/tiles.txt" "$dir/delta.vrt"
    gdal_polygonize.py -q -8 "$dir/delta.vrt" -f GPKG "$dir/mangroves.gpkg" mangroves dn

    ogr2ogr -f PostgreSQL "$PG" "$dir/mangroves.gpkg" mangroves \
        -nln "stage.mangroves_$year" -overwrite -lco GEOMETRY_NAME=geom -t_srs EPSG:4326
done

echo "== settlements (OSM place=*)"
ogr2ogr -f PostgreSQL "$PG" "$RAW/osm/nigeria-250101.osm.pbf" points \
    -nln stage.osm_places -overwrite -lco GEOMETRY_NAME=geom \
    -where "place IN ('city','town','village','hamlet','isolated_dwelling','locality')" \
    -spat 2 3 10 8 \
    -select "osm_id,name,place"

echo "done"
