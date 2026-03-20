"""Exceptions used throughout the package."""

import typing

if typing.TYPE_CHECKING:
    from fastcc.qos import QoS


class FastCCError(Exception):
    """Base exception class for FastCC-related errors."""


class MqttConnectionError(FastCCError):
    """Raised when a connection to the MQTT broker fails."""

    def __init__(self, *, host: str, port: int) -> None:
        super().__init__(f"Could not connect to MQTT broker on '{host}:{port}'")
        self.host = host
        self.port = port


class InvalidQoSLevelError(FastCCError):
    """Raised when an an invalid QoS level was used."""

    def __init__(self, *, qos: QoS) -> None:
        super().__init__(f"Invalid QoS level: {qos}.")
        self.qos = qos


class OperationError(FastCCError):
    """Raised when an operation fails.

    Parameters
    ----------
    operation
        The name of the operation that failed.
    topic
        The topic associated with the operation.
    reason
        An optional message describing the reason for the failure.
    """

    def __init__(self, *, operation: str, topic: str) -> None:
        message = f"{operation} on topic '{topic}' failed"
        super().__init__(message)
        self.operation = operation
        self.topic = topic


class OperationTimeoutError(FastCCError):
    """Raised when an operation times out.

    Parameters
    ----------
    operation
        The name of the operation that timed out.
    topic
        The topic associated with the operation.
    timeout
        The duration in seconds after which the operation timed out.
    """

    def __init__(
        self,
        *,
        operation: str,
        topic: str,
        timeout: float,
    ) -> None:
        super().__init__(
            f"{operation} on topic '{topic}' timed out after {timeout}s",
        )
        self.operation = operation
        self.topic = topic
        self.timeout = timeout


class CodecConflictError(FastCCError):
    """Raised when a codec with a conflicting tag is registered."""

    def __init__(self, *, tag: int) -> None:
        super().__init__(f"Codec with tag {tag} is already registered")
        self.tag = tag


class SerializationError(FastCCError):
    """Raised when serialization or deserialization fails."""


class InvalidCodecTagError(SerializationError):
    """Raised when a codec has an invalid tag."""

    def __init__(self, *, tag: typing.Any) -> None:
        super().__init__(f"Invalid codec tag: {tag}")
        self.tag = tag
