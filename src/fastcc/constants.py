"""Module defining immutable values used across the codebase."""

import datetime
import typing

DEFAULT_MQTT_HOST: typing.Final[str] = "127.0.0.1"
"""Default IP address of the MQTT-Broker to connect to."""

DEFAULT_MQTT_PORT: typing.Final[int] = 1883
"""Default port number of the MQTT-Broker to connect to."""

DEFAULT_MESSAGING_TIMEOUT: typing.Final[datetime.timedelta] = (
    datetime.timedelta(seconds=5)
)
"""Default timeout for messaging operations (publish, subscribe, unsubscribe)."""  # noqa: E501

MAX_PAYLOAD_SIZE: typing.Final[int] = 1_048_576
"""Maximum allowed payload size for deserialization (1 MB)."""

FLOAT_BYTE_LENGTH = 8
"""Number of bytes used to represent a float in the custom serialization format (IEEE 754 double-precision)."""  # noqa: E501

BOOL_FALSE_BYTE = b"\x00"
"""Byte representation of the boolean value ``False`` in the custom serialization format."""  # noqa: E501

BOOL_TRUE_BYTE = b"\x01"
"""Byte representation of the boolean value ``True`` in the custom serialization format."""  # noqa: E501

MAX_CODEC_TAG = 0xFF
"""Maximum allowed codec tag value (255) for FastCC serialization."""

TOPIC_SEPARATOR: typing.Final[str] = "/"
"""Separator used in MQTT topics."""

SINGLE_LEVEL_WILDCARD: typing.Final[str] = "+"
"""Wildcard character used in MQTT topics to match exactly one level."""

MULTI_LEVEL_WILDCARD: typing.Final[str] = "#"
"""Wildcard character used in MQTT topics to match any number of levels."""

WILDCARD_PARAMETER_NAME: typing.Final[str] = "wildcard"
"""Name of the parameter used to capture wildcard segments in route handlers."""
