"""Module containing the `MQTTError` exception class."""


class MQTTError(Exception):
    """Exception class for communicating errors over MQTT."""

    def __init__(self, message: str, error_code: int) -> None:
        self._message = message
        self._error_code = error_code

    @property
    def error_code(self) -> int:
        """Error code of the exception."""
        return self._error_code

    @property
    def message(self) -> str:
        """Message of the exception."""
        return self._message
