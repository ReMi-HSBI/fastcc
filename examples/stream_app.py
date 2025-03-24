"""Simple app example."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
from collections.abc import AsyncIterator

import fastcc

router = fastcc.Router()


@router.route("greet")
async def greet(
    name: str,
    *,
    database: dict[str, int],
) -> AsyncIterator[str]:
    """Greet a user.

    Parameters
    ----------
    name
        The name of the user.
        Autofilled by fastcc.
    database
        The database.
        Autofilled by fastcc.

    Yields
    ------
    str
        The greeting message.
    """
    # ... do some async work
    await asyncio.sleep(0.1)

    database[name] += 1
    occurrence = database[name]
    yield f"Hello, {name}! Saw you {occurrence} times!"
    yield f"Hello, {name}! Saw you {occurrence} times (2x)!"
    # yield "s"


async def main() -> None:
    """Run the app."""
    logging.basicConfig(level=logging.DEBUG)

    database: dict[str, int] = {"Alice": 0, "Bob": 0}
    app = fastcc.FastCC("test.mosquitto.org")
    app.add_router(router)
    app.add_injector(database=database)
    app.add_exception_handler(
        KeyError,
        lambda e: fastcc.MQTTError(repr(e), 404),
    )

    await app.run()


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
