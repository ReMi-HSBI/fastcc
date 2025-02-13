"""Security utilities."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from paho.mqtt.properties import Properties


from fastcc.exceptions import MQTTError


def verify_correlation_data(
    properties: Properties | None,
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
    correlation_data = getattr(properties, "CorrelationData", None)
    return correlation_data == expected_correlation_data


def check_for_errors(properties: Properties | None, payload: bytes) -> None:
    """Check for thrown errors in a response.

    Parameters
    ----------
    properties
        Properties of the response.
    payload
        Payload of the response.

    Raises
    ------
    MQTTError
        If an error is found in the response.
    """
    user_properties = getattr(properties, "UserProperty", [])
    error_code = find_user_property("error", user_properties)
    if error_code is not None:
        raise MQTTError(
            payload.decode(),
            int(error_code) if error_code.isdigit() else None,
        )


def find_user_property(
    field: str,
    user_properties: list[tuple[str, str]],
) -> str | None:
    """Find a user property in a list of user properties.

    Parameters
    ----------
    field
        Field to find.
    user_properties
        List of user properties.

    Returns
    -------
    str
        Value of the user property.
    None
        If the user property is not found.
    """
    for key, value in user_properties:
        if key == field:
            return value
    return None
