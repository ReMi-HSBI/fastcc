"""Utilities related to MQTT."""

from __future__ import annotations

import enum
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

from fastcc.exceptions import MQTTError


class QoS(enum.IntEnum):
    """Quality of Service levels [1]_.

    References
    ----------
    .. [1] https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html#_Toc3901234
    """

    #: The message is delivered at most once, or it is not delivered at all.
    AT_MOST_ONCE = 0

    #: The message is always delivered at least once.
    AT_LEAST_ONCE = 1

    #: The message is always delivered exactly once.
    EXACTLY_ONCE = 2


def get_message_property(
    message: aiomqtt.Message,
    property_name: str,
) -> typing.Any | None:
    """Get a property of a message.

    Parameters
    ----------
    message
        Message to get the property from.
    property_name
        Name of the property to get.

    Returns
    -------
    Any
        Property value.
    None
        If the message has no such property.
    """
    if (properties := message.properties) is None:
        return None

    return getattr(properties, property_name, None)


def get_response_topic(message: aiomqtt.Message) -> str | None:
    """Get the response topic of a message.

    Parameters
    ----------
    message
        Message to get the response topic from.

    Returns
    -------
    str
        Response topic.
    None
        If the message has no response topic.
    """
    return get_message_property(message, "ResponseTopic")


def get_correlation_data(message: aiomqtt.Message) -> bytes | None:
    """Get the correlation data of a message.

    Parameters
    ----------
    message
        Message to get the correlation data from.

    Returns
    -------
    bytes
        Correlation data.
    None
        If the message has no correlation data.
    """
    return get_message_property(message, "CorrelationData")


def get_user_properties(
    message: aiomqtt.Message,
) -> list[tuple[str, str]] | None:
    """Get the user properties of a message.

    Parameters
    ----------
    message
        Message to get the user properties from.

    Returns
    -------
    list[tuple[str, str]]
        User properties.
    None
        If the message has no correlation data.
    """
    return get_message_property(message, "UserProperty")


def get_user_property(
    name: str,
    user_properties: list[tuple[str, str]] | None,
) -> str | None:
    """Find a user property in a list of user properties.

    Parameters
    ----------
    name
        Name of the user property.
    user_properties
        List of user properties.

    Returns
    -------
    str
        Value of the user property.
    None
        If the user property is not found.
    """
    if user_properties is None:
        return None

    for key, value in user_properties:
        if key == name:
            return value
    return None


def check_error_code(message: aiomqtt.Message) -> None:
    """Check if an error is set in the message.

    Parameters
    ----------
    message
        Message to check for an error.

    Raises
    ------
    MQTTError
        If an error is set in the message.
    """
    assert isinstance(message.payload, bytes)  # noqa: S101

    if (user_properties := get_user_properties(message)) is None:
        return

    if (error_code := get_user_property("error", user_properties)) is None:
        return

    raise MQTTError(
        message.payload.decode(),
        int(error_code) if error_code.isdigit() else None,
    )


def verify_correlation_data(
    message: aiomqtt.Message,
    expected_correlation_data: bytes,
) -> bool:
    """Verify if the correlation data of a message is valid.

    Parameters
    ----------
    properties
        Properties of the message.
    expected_correlation_data
        Correlation data to verify.

    Returns
    -------
    bool
        True if the correlation data is valid, False otherwise.
    """
    if (correlation_data := get_correlation_data(message)) is None:
        return False

    return correlation_data == expected_correlation_data
