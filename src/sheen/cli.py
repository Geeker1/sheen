from pathlib import Path
from typing import Annotated

import typer

from sheen.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="Niger Delta oil spill data pipeline.")
ingest_app = typer.Typer(no_args_is_help=True, help="Load data.")
app.add_typer(ingest_app, name="ingest")


@app.callback()
def _main() -> None:
    configure_logging()


@app.command()
def migrate() -> None:
    """Create or update the database tables."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


FromFile = Annotated[Path | None, typer.Option(help="Use a saved file instead of downloading.")]
Force = Annotated[bool, typer.Option(help="Carry on even if the register hasn't changed.")]
UNCHANGED = "The register hasn't changed since the last download, so there's nothing to do."


@ingest_app.command("spills")
def ingest_spills(from_file: FromFile = None, force: Force = False) -> None:
    """Download the NOSDRA spill register and save it as published."""
    from sheen.ingest import nosdra

    typer.echo(nosdra.ingest(from_file, force) or UNCHANGED)


@ingest_app.command("boundaries")
def ingest_boundaries() -> None:
    """Load the state and local government boundaries."""
    from sheen.ingest import boundaries

    boundaries.ingest()


@ingest_app.command("layers")
def ingest_layers() -> None:
    """Load the mangrove and settlement data prepared by the GDAL script."""
    from sheen.ingest import layers

    layers.promote()


@app.command()
def validate() -> None:
    """Check the latest download and save the results."""
    from sheen.validation import engine

    typer.echo(engine.validate())


@app.command()
def analyse() -> None:
    """Work out what was near each spill and update the summaries."""
    from sheen.analysis import exposure

    typer.echo(exposure.analyse())


@app.command()
def run(from_file: FromFile = None, force: Force = False) -> None:
    """Download, check and analyse, in one go."""
    from sheen.analysis import exposure
    from sheen.ingest import nosdra
    from sheen.validation import engine

    if nosdra.ingest(from_file, force) is None:
        typer.echo(UNCHANGED)
        return
    engine.validate()
    typer.echo(exposure.analyse())
