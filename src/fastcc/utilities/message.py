"""Module defining message utilities."""

import aiomqtt

from fastcc.exceptions import ErrorCode


def get_correlation_id(message: aiomqtt.Message) -> str | None:
    """Extract the correlation ID from the given message.

    Parameters
    ----------
    message
        Message from which to extract the correlation ID.

    Returns
    -------
    str | None
        Correlation ID if present, otherwise ``None``.
    """
    if message.properties is None:
        return None

    data: bytes | None = getattr(message.properties, "CorrelationData", None)
    if data is None:
        return None

    return data.decode()


def get_response_topic(message: aiomqtt.Message) -> str | None:
    """Extract the response topic from the given message.

    Parameters
    ----------
    message
        Message from which to extract the response topic.

    Returns
    -------
    str | None
        Response topic if present, otherwise ``None``.
    """
    if message.properties is None:
        return None

    return getattr(message.properties, "ResponseTopic", None)


def get_error_code(message: aiomqtt.Message) -> ErrorCode | None:
    """Extract the error code from the given message.

    Parameters
    ----------
    message
        Message from which to extract the error code.

    Returns
    -------
    ErrorCode | None
        Error code if present, otherwise ``None``.
    """
    user_properties = getattr(message.properties, "UserProperty", [])
    raw_error_code: str | None = next(
        (t[1] for t in user_properties if t[0] == "error"),
        None,
    )

    if raw_error_code is None:
        return None

    return ErrorCode(int(raw_error_code))
