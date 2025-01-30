"""Utilities related to MQTT."""

from __future__ import annotations

import enum


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
