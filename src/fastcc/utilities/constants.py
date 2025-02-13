"""Constant values."""

from __future__ import annotations

import typing

#: Default stream chunk size.
DEFAULT_STREAM_CHUNK_SIZE: typing.Final[int] = 1024

#: Injector field name for the message.
MESSAGE_INJECTOR_FIELD: typing.Final[str] = "message"

#: Injector field name for the chunk size.
CHUNK_SIZE_INJECTOR_FIELD: typing.Final[str] = "chunk_size"

RESERVED_INJECTOR_FIELDS: typing.Final[set[str]] = {
    MESSAGE_INJECTOR_FIELD,
    CHUNK_SIZE_INJECTOR_FIELD,
}
