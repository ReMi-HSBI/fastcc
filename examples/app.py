"""Simple app example."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import typing

import fastcc

router = fastcc.Router()


@router.route("greet")
async def greet(name: str, *, database: dict[str, typing.Any]) -> str:
    """Greet a user.

    Parameters
    ----------
    name
        The name of the user.
        Autofilled by fastcc.
    database
        The database.
        Autofilled by fastcc.

    Returns
    -------
    str
        The greeting message.
    """
    # ... do some async work
    await asyncio.sleep(0.1)

    if name in database:
        return f"Hello, {name}! Welcome back!"
    return f"Hello, {name}!"


async def main() -> None:
    """Run the app."""
    logging.basicConfig(level=logging.INFO)

    database: dict[str, typing.Any] = {}
    app = fastcc.FastCC("localhost")
    app.add_router(router)
    app.add_injector(database=database)

    await app.run()


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
