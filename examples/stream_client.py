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
    logging.basicConfig(level=logging.DEBUG)

    async with fastcc.Client("test.mosquitto.org") as client:
        try:
            async for response in client.stream(
                "greet",
                "Charlie",
                response_type=str,
            ):
                _logger.info("response: %r", response)
        except fastcc.MQTTError as e:
            details = f"An error occurred on the server: {e.message}"
            _logger.error(details)

        async for response in client.stream(
            "greet",
            "Alice",
            response_type=str,
        ):
            _logger.info("response: %r", response)


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
