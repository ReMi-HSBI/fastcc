"""Module defining the ``QoS`` enum."""

import enum

__all__ = ["QoS"]


class QoS(enum.IntEnum):
    """Quality of Service levels for MQTT messages.

    For more details, see the MQTT specification [4]_.

    References
    ----------
    .. [4] https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html#_Toc3901234
    """

    AT_MOST_ONCE = 0
    """The message is delivered at most once, or it is not delivered at all."""

    AT_LEAST_ONCE = 1
    """The message is always delivered at least once."""

    EXACTLY_ONCE = 2
    """The message is always delivered exactly once."""
