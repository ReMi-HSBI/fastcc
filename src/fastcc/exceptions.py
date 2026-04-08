"""Exceptions used throughout the package."""


class FastCCError(Exception):
    """Base exception class for FastCC-related errors."""


class MqttConnectionError(FastCCError):
    """Raised when a connection to the MQTT broker fails."""

    def __init__(self, *, host: str, port: int) -> None:
        super().__init__(f"Failed to connect to MQTT broker on '{host}:{port}'")
        self.host = host
        self.port = port
