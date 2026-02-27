"""Module defining exceptions raised across the codebase."""

import typing

__all__ = ["FastCCError", "MessagingError", "SerializationError"]


class FastCCError(Exception):
    """Base exception class for FastCC-related errors."""

    def __init__(self, msg: str, *msg_args: typing.Any) -> None:
        self._msg = msg
        self._msg_args = msg_args

    def __str__(self) -> str:
        return self._msg % self._msg_args if self._msg_args else self._msg

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"


class SerializationError(FastCCError):
    """Exception raised when serialization or deserialization fails."""


class MessagingError(FastCCError):
    """Exception raised when messaging operations (publish, subscribe, etc.) fail."""  # noqa: E501
