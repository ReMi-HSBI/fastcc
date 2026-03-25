"""Utility functions used across the codebase."""

import typing

if typing.TYPE_CHECKING:
    import aiomqtt

from fastcc.exceptions import MalformedMessageError


def get_correlation_id(message: aiomqtt.Message) -> str:
    """Extract the correlation ID from the MQTT message properties.

    Parameters
    ----------
    message
        The MQTT message from which to extract the correlation ID.

    Returns
    -------
    str
        The correlation ID of the message.

    Raises
    ------
    AttributeError
        If the message does not have a correlation ID.
    """
    error_message = "Message has no correlation ID"
    if message.properties is None:
        raise AttributeError(error_message)

    cid: bytes | None = getattr(message.properties, "CorrelationData", None)
    if cid is None:
        raise AttributeError(error_message)

    return cid.decode()


def get_status_code(message: aiomqtt.Message) -> int:
    """Extract the status code from the MQTT message properties.

    Parameters
    ----------
    message
        The MQTT message from which to extract the status code.

    Returns
    -------
    int
        The status code of the message.

    Raises
    ------
    AttributeError
        If the message does not have a status code.
    MalformedMessageError
        If the status code value is not a valid integer.
    """
    error_message = "Message has no status code"
    if message.properties is None:
        raise AttributeError(error_message)

    user_properties: list[tuple[str, str]] | None = getattr(
        message.properties,
        "UserProperty",
        None,
    )
    if user_properties is None:
        raise AttributeError(error_message)

    for key, value in user_properties:
        if key == "status_code":
            try:
                return int(value)
            except ValueError as exc:
                error_message = f"Invalid status code value: {value}"
                raise MalformedMessageError(error_message) from exc

    raise AttributeError(error_message)
