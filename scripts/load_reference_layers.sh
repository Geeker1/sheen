#!/usr/bin/env bash
# Load the mangrove and settlement data into the `stage` schema using GDAL.
#
# It runs in the GDAL container, so the main app doesn't need GDAL:
#   docker compose run --rm gdal /work/scripts/load_reference_layers.sh
# Then move the data into the main tables with:
#   sheen ingest layers
#
# The files it reads (downloaded by `make reference-data`):
#   data/raw/gmw/gmw_v3_{2007,2020}_gtiff.zip   Global Mangrove Watch maps
#   data/raw/osm/nigeria-250101.osm.pbf         OpenStreetMap, 1 January 2025
set -euo pipefail

# Database settings, defaulting to the local database.
PG="PG:host=${PGHOST:-db} port=${PGPORT:-5432} dbname=${PGDATABASE:-sheen} user=${PGUSER:-sheen} password=${PGPASSWORD:-sheen}"
RAW=/work/data/raw
WORK=/work/data/work
mkdir -p "$WORK"

# The mangrove map comes in tiles named after their top-left corner. These
# cover the coast from Lagos to the Cameroon border.
TILE_GLOB='GMW_N0[3-8]E00[2-9]_*.tif'

for year in 2007 2020; do
    echo "== mangroves $year"
    zip="$RAW/gmw/gmw_v3_${year}_gtiff.zip"
    dir="$WORK/gmw_$year"
    rm -rf "$dir" && mkdir -p "$dir"
    # GDAL reads the tiles straight from the zip file, so nothing is unpacked.
    python3 -c "import fnmatch, sys, zipfile
names = zipfile.ZipFile(sys.argv[1]).namelist()
print('\n'.join('/vsizip/' + sys.argv[1] + '/' + n for n in names if fnmatch.fnmatch(n.split('/')[-1], sys.argv[2])))" \
        "$zip" "$TILE_GLOB" > "$dir/tiles.txt"
    echo "   $(wc -l < "$dir/tiles.txt") tiles"

    # 0 means no mangrove. Treat it as empty so only mangrove becomes shapes.
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
