import asyncio
import logging
from pathlib import Path

import uvloop
import typer
from appdirs import user_data_dir
from loguru import logger
from rich.logging import Console, RichHandler
from rich.theme import Theme

uvloop.install()

from . import __name__ as __product__, __author__, __url__, __version__
from .config import config
from .bot.fix import patch_pyrogram

patch_pyrogram()

from .bot.pool import start as start_pool
from .bot.father import FatherBot
from .model import BaseModel, db


def formatter(record):
    extra = record["extra"]
    scheme = extra.get("scheme", None)
    if scheme == "group":
        id = extra.get("id", "starting")
        return f"[medium_purple4]Bot ({id})[/] {{message}}"
    else:
        return "[green][/] {message}"


logger.remove()
logging.addLevelName(5, "TRACE")
logger.add(
    RichHandler(
        console=Console(stderr=True, theme=Theme({"logging.level.trace": "gray50"})),
        markup=True,
        rich_tracebacks=True,
    ),
    format=formatter,
    level=0,
)

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command(help=f"Bot server for [orange3]{__product__.capitalize()}[/] {__version__}.")
def main(
    config_file: Path = typer.Argument(
        ...,
        envvar=f"{__product__.upper()}_CONFIG",
        dir_okay=False,
        allow_dash=True,
        help="Config toml file",
    )
):
    config.reload_conf(config_file)
    basedir = Path(config.get("basedir", user_data_dir(__product__)))
    logger.debug(f'Now using basedir at "{basedir.absolute()}"')
    basedir.mkdir(parents=True, exist_ok=True)
    db.init(str(basedir / f"{__product__}.db"), pragmas={"journal_mode": "wal"})
    db.create_tables(BaseModel.__subclasses__())

    async def async_main():
        await asyncio.gather(FatherBot(config["father.token"]).start(), start_pool())

    asyncio.run(async_main())
