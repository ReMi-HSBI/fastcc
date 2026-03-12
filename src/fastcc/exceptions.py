"""Exceptions used throughout the package."""


class FastCCError(Exception):
    """Base exception class for FastCC-related errors."""


class MqttConnectionError(FastCCError):
    """Raised when a connection to the MQTT broker fails."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        super().__init__(f"Could not connect to MQTT broker at {host}:{port}")
