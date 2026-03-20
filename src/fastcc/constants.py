"""Constant values used throughout the package."""

import typing

DEFAULT_MQTT_HOST: typing.Final[str] = "127.0.0.1"
"""Default IP address of the MQTT-Broker to connect to."""

DEFAULT_MQTT_PORT: typing.Final[int] = 1883
"""Default port number of the MQTT-Broker to connect to."""

MAX_CODEC_TAG: typing.Final[int] = 255
"""Maximum valid codec tag value (inclusive)."""

BOOL_FALSE_BYTE: typing.Final[bytes] = b"\x00"
"""Byte representation of the boolean value ``False``."""

BOOL_TRUE_BYTE: typing.Final[bytes] = b"\x01"
"""Byte representation of the boolean value ``True``."""

FLOAT_BYTE_LENGTH: typing.Final[int] = 8
"""Number of bytes used to encode a floating-point number."""
