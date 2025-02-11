"""Simple client example."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys

import fastcc

_logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the app."""
    logging.basicConfig(level=logging.INFO)

    async with fastcc.Client("localhost") as client:
        try:
            response = await client.request(
                "greet",
                "Charlie",
                response_type=str,
            )
        except fastcc.MQTTError as e:
            details = f"An error occurred on the server: {e.message}"
            _logger.error(details)

        response = await client.request("greet", "Alice", response_type=str)
        _logger.info("response: %r", response)


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
