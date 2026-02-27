"""Module defining annotation types."""

import typing
from collections.abc import Awaitable, Callable

type AnyCallable = Callable[..., typing.Any]
"""Type alias for any callable."""

type RouteHandler = Callable[..., Awaitable[typing.Any]]
"""Type alias for route handler functions."""
