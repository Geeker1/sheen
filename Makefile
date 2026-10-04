.PHONY: help up down migrate reference-data layers run api web test lint check

UV := uv run --env-file .env

help:   ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up:     ## Start PostGIS and local S3
	cp -n .env.example .env || true
	docker compose up -d db s3

down:   ## Stop containers (keeps data)
	docker compose down

migrate: ## Apply database migrations
	$(UV) sheen migrate

reference-data: ## Download boundary, mangrove and OSM source files (~760 MB)
	mkdir -p data/raw/gmw data/raw/osm
	for y in 2007 2020; do \
	  test -f data/raw/gmw/gmw_v3_$${y}_gtiff.zip || curl -fL -o data/raw/gmw/gmw_v3_$${y}_gtiff.zip \
	    "https://zenodo.org/records/6894273/files/gmw_v3_$${y}_gtiff.zip?download=1"; \
	done
	test -f data/raw/osm/nigeria-250101.osm.pbf || curl -fL -o data/raw/osm/nigeria-250101.osm.pbf \
	  https://download.geofabrik.de/africa/nigeria-250101.osm.pbf

layers: ## Load boundaries, mangroves and settlements (needs reference-data)
	$(UV) sheen ingest boundaries
	docker compose run --rm -T gdal /work/scripts/load_reference_layers.sh
	$(UV) sheen ingest layers

run:    ## Ingest the live NOSDRA register, validate, analyse
	$(UV) sheen run

api:    ## Serve the API on :8000 (GraphiQL at /graphql)
	$(UV) uvicorn sheen.api.app:app --reload --port 8000

web:    ## Serve the map on :5173 (needs `make api`)
	cd web && npm install && npm run dev

test:   ## Unit + PostGIS integration tests
	uv run pytest

lint:   ## Ruff + mypy
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

check: lint test ## Everything CI runs for Python
