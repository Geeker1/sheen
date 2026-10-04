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
