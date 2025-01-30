<p align="center">
    <img src="https://github.com/ReMi-HSBI/fastcc/blob/main/docs/src/static/images/fastci_logo.svg?raw=true" alt="drawing" width="33%"/>
</p>

# FastCC

Framework for component communication with [MQTT](https://mqtt.org) and [Protocol Buffers](https://protobuf.dev) :boom:.

- Lightweight :zap:
- Efficient :rocket:
- Developer-friendly :technologist:

This framework is built on top of [empicano](https://github.com/empicano)'s [aiomqtt](https://github.com/empicano/aiomqtt).

## Example

```python
import asyncio
import contextlib
import logging
import os
import sys
import typing

import aiomqtt
import fastcc

router = fastcc.CCRouter()


@router.route("example")
async def example(name: str, *, database: dict[str, typing.Any]) -> str:
    database[name] = 1
    print(database)
    return f"Hello, {name}!"


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    database = {}
    mqtt_client = aiomqtt.Client(
        "test.mosquitto.org",
        protocol=aiomqtt.ProtocolVersion.V5,
    )
    app = fastcc.FastCC(mqtt_client)
    app.add_router(router)
    app.add_injector(database=database)

    async with mqtt_client:
        await app.run()


# https://github.com/empicano/aiomqtt?tab=readme-ov-file#note-for-windows-users
if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
```
