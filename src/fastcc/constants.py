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

TOPIC_SEPARATOR: typing.Final[str] = "/"
"""Separator used in MQTT topics."""

DEFAULT_RESPONSE_TOPIC_PREFIX: typing.Final[str] = TOPIC_SEPARATOR.join((
    "fastcc",
    "responses",
))
"""Default prefix for MQTT topics used for receiving responses in request/response communication."""  # noqa: E501

STATUS_CODE_SUCCESS: typing.Final[int] = 0
"""Status code indicating a successful operation."""
