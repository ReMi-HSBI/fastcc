"""Module containing the `MQTTError` exception class."""


class FastCCError(Exception):
    """Base exception of FastCC."""


class MQTTError(FastCCError):
    """Exception class for communicating errors over MQTT."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        self._message = message
        self._error_code = error_code
        super().__init__(message)

    @property
    def error_code(self) -> int | None:
        """Error code of the exception."""
        return self._error_code

    @property
    def message(self) -> str:
        """Message of the exception."""
        return self._message
