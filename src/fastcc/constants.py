"""Constant values used throughout the package."""

import typing

DEFAULT_MQTT_HOST: typing.Final[str] = "127.0.0.1"
"""Default IP address of the MQTT-Broker to connect to."""

DEFAULT_MQTT_PORT: typing.Final[int] = 1883
"""Default port number of the MQTT-Broker to connect to."""

TOPIC_SEPARATOR: typing.Final[str] = "/"
"""Separator used in MQTT topics."""

DEFAULT_RESPONSE_TOPIC: typing.Final[str] = TOPIC_SEPARATOR.join((
    "fastcc",
    "responses",
))
"""Default topic used for receiving responses in request/response communication."""  # noqa: E501

STATUS_CODE_SUCCESS: typing.Final[int] = 0
"""Status code indicating a successful operation."""
