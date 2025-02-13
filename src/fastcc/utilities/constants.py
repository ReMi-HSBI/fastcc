"""Constant values."""

from __future__ import annotations

import typing

#: Injector field name for the message.
MESSAGE_INJECTOR_FIELD: typing.Final[str] = "message"

RESERVED_INJECTOR_FIELDS: typing.Final[set[str]] = {MESSAGE_INJECTOR_FIELD}
