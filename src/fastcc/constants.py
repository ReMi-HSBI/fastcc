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

STATUS_CODE_FAILURE: typing.Final[int] = -1
"""Status code indicating a failed operation."""

PATH_PARAMETER_PATTERN: typing.Final[str] = r"\{(\w+)\}"
"""Regular expression pattern for matching path parameters in topic patterns."""

MULTI_LEVEL_WILDCARD: typing.Final[str] = "#"
"""Multi-level wildcard character used in MQTT topic patterns."""

SINGLE_LEVEL_WILDCARD: typing.Final[str] = "+"
"""Single-level wildcard character used in MQTT topic patterns."""

WILDCARD_PARAMETER_NAME: typing.Final[str] = "wildcard"
"""Name of the parameter used to inject wildcard values in handler functions."""
