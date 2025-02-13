"""Type aliases for improved type safety and code clarity."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from fastcc.exceptions import MQTTError
    from fastcc.utilities.type_definitions import Packet

    Routable = Callable[..., Awaitable[Packet | None] | AsyncIterator[Packet]]
    ExceptionHandler = Callable[[Exception], MQTTError]
