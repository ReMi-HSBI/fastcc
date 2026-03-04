"""Module defining annotation types."""

import typing
from collections.abc import AsyncIterator, Awaitable, Callable

type AnyCallable = Callable[..., typing.Any]
"""Type alias for any callable."""

type RouteHandler = Callable[
    ...,
    Awaitable[typing.Any] | AsyncIterator[typing.Any],
]
"""Type alias for route handler functions."""
