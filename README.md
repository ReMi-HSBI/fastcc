<p align="center">
    <img src="https://github.com/ReMi-HSBI/fastcc/blob/main/docs/src/static/images/fastci_logo.svg?raw=true" alt="drawing" width="33%"/>
</p>

# FastCC

<a href="https://docs.astral.sh/ruff">
  <img
    src="https://img.shields.io/badge/ruff-⚡-261230.svg?style=flat-square"
    alt="Ruff"
  />
</a>
<a href="https://mypy-lang.org">
  <img
    src="https://img.shields.io/badge/mypy-📝-2a6db2.svg?style=flat-square"
    alt="Mypy"
  />
</a>
<a href="https://gitmoji.dev">
  <img
    src="https://img.shields.io/badge/gitmoji-😜%20😍-FFDD67.svg?style=flat-square"
    alt="Gitmoji"
  />
</a>

Framework for component communication with [MQTT](https://mqtt.org) and [Protocol Buffers](https://protobuf.dev) :boom:.

- Lightweight :zap:
- Efficient :rocket:
- Developer-friendly :technologist:

This framework is built on top of [empicano](https://github.com/empicano)'s [aiomqtt](https://github.com/empicano/aiomqtt).

## Example

```python
# app.py
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
```

```python
# client.py
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
        response = await client.request("greet", "Justin", response_type=str)
        _logger.info("response: %r", response)


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())

```
