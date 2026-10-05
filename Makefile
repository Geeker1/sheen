.PHONY: help up down migrate reference-data layers run api web test lint check

UV := uv run --env-file .env

help:   ## Show the commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up:     ## Start the database and a local S3
	cp -n .env.example .env || true
	docker compose up -d db s3

down:   ## Stop them (the data is kept)
	docker compose down

migrate: ## Create or update the tables
	$(UV) sheen migrate

reference-data: ## Download the mangrove and OpenStreetMap files (about 760 MB)
	mkdir -p data/raw/gmw data/raw/osm
	for y in 2007 2020; do \
	  test -f data/raw/gmw/gmw_v3_$${y}_gtiff.zip || curl -fL -o data/raw/gmw/gmw_v3_$${y}_gtiff.zip \
	    "https://zenodo.org/records/6894273/files/gmw_v3_$${y}_gtiff.zip?download=1"; \
	done
	test -f data/raw/osm/nigeria-250101.osm.pbf || curl -fL -o data/raw/osm/nigeria-250101.osm.pbf \
	  https://download.geofabrik.de/africa/nigeria-250101.osm.pbf

layers: ## Load boundaries, mangroves and settlements
	$(UV) sheen ingest boundaries
	docker compose run --rm -T gdal /work/scripts/load_reference_layers.sh
	$(UV) sheen ingest layers

run:    ## Download the register, check it and analyse it
	$(UV) sheen run

api:    ## Start the API on port 8000
	$(UV) uvicorn sheen.api.app:app --reload --port 8000

web:    ## Start the map on port 5173 (needs the API)
	cd web && npm install && npm run dev

test:   ## Run the tests
	uv run pytest

lint:   ## Check code style and types
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

check: lint test ## Run all the Python checks
