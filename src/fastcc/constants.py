"""Module defining immutable values used across the codebase."""

import typing

DEFAULT_MQTT_HOST: typing.Final[str] = "127.0.0.1"
"""Default IP address of the MQTT-Broker to connect to."""

DEFAULT_MQTT_PORT: typing.Final[int] = 1883
"""Default port number of the MQTT-Broker to connect to."""
