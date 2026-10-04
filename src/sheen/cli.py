from pathlib import Path
from typing import Annotated

import typer

from sheen.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="Niger Delta oil spill data pipeline.")
ingest_app = typer.Typer(no_args_is_help=True, help="Fetch source data.")
app.add_typer(ingest_app, name="ingest")


@app.callback()
def _main() -> None:
    configure_logging()


@ingest_app.command("spills")
def ingest_spills(
    from_file: Annotated[
        Path | None, typer.Option(help="Load a saved snapshot instead of fetching live.")
    ] = None,
) -> None:
    """Fetch the NOSDRA spill register into raw.spill_reports."""
    from sheen.ingest import nosdra

    typer.echo(nosdra.ingest(from_file))


@app.command()
def migrate() -> None:
    """Apply database migrations."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


@ingest_app.command("boundaries")
def ingest_boundaries() -> None:
    """Load state and LGA boundaries into ref.admin_areas."""
    from sheen.ingest import boundaries

    boundaries.ingest()


@app.command()
def validate() -> None:
    """Validate the latest spill snapshot into clean.spills."""
    from sheen.validation import engine

    typer.echo(engine.validate())


@ingest_app.command("layers")
def ingest_layers() -> None:
    """Promote GDAL-staged mangrove and settlement layers into ref.*."""
    from sheen.ingest import layers

    layers.promote()


@app.command()
def analyse() -> None:
    """Compute per-spill exposure and refresh regional/operator summaries."""
    from sheen.analysis import exposure

    typer.echo(exposure.analyse())


@app.command()
def run(
    from_file: Annotated[
        Path | None, typer.Option(help="Load a saved snapshot instead of fetching live.")
    ] = None,
) -> None:
    """Ingest, validate and analyse in one go (the scheduled job)."""
    from sheen.analysis import exposure
    from sheen.ingest import nosdra
    from sheen.validation import engine

    nosdra.ingest(from_file)
    engine.validate()
    typer.echo(exposure.analyse())
