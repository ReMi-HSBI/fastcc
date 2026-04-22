"""Exceptions used throughout the package."""


class FastCCError(Exception):
    """Base exception class for FastCC-related errors."""


class MqttConnectionError(FastCCError):
    """Raised when a connection to the MQTT broker fails."""

    def __init__(self, *, host: str, port: int) -> None:
        super().__init__(f"Failed to connect to MQTT broker on '{host}:{port}'")
        self.host = host
        self.port = port


class RequestError(FastCCError):
    """Raised when an MQTT request fails."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class CodecError(FastCCError):
    """Raised when encoding or decoding data fails."""


class CodecNotFoundError(CodecError):
    """Raised when a codec with a specific type is not found in the registry."""

    def __init__(self, codec_type: int) -> None:
        super().__init__(f"Codec with type {codec_type} not found in registry")
        self.codec_type = codec_type


class RouteValidationError(FastCCError):
    """Raised when a route pattern or handler is invalid."""
