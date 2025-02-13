"""Type definitions for improved type safety and code clarity."""
from __future__ import annotations

from google.protobuf.message import Message

Packet = bytes | str | int | float | Message | None
