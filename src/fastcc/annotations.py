"""Module defining annotation-types used across the codebase."""

import google.protobuf.message as pb2_message

type Packet = bytes | str | int | float | bool | pb2_message.Message | None
"""Union of allowed payload types that can be processed by FastCC."""
