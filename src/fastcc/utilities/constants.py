"""Constant values."""

from __future__ import annotations

import typing

#: Default timeout to wait for a response after request.
DEFAULT_PUBLISH_TIMEOUT: typing.Final[float] = 5.0

#: Default timeout to wait for a response after request.
DEFAULT_SUBSCRIBE_TIMEOUT: typing.Final[float] = 5.0

#: Default timeout to wait for a response after request.
DEFAULT_UNSUBSCRIBE_TIMEOUT: typing.Final[float] = 5.0

#: Default timeout to wait for a response after request.
DEFAULT_RESPONSE_TIMEOUT: typing.Final[float] = 5.0

#: Injector field name for the message.
MESSAGE_INJECTOR_FIELD: typing.Final[str] = "message"

RESERVED_INJECTOR_FIELDS: typing.Final[set[str]] = {MESSAGE_INJECTOR_FIELD}
