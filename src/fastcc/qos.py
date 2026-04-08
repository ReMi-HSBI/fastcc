"""Module defining the ``QoS`` enum."""

import enum


class QoS(enum.IntEnum):
    """Selectable Quality of Service levels for MQTT messages.

    For more details, see the
    `MQTT specification <https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html#_Toc3901234>`_.
    """

    AT_MOST_ONCE = 0
    """The message is delivered at most once, or it is not delivered at all."""

    AT_LEAST_ONCE = 1
    """The message is always delivered at least once."""

    EXACTLY_ONCE = 2
    """The message is always delivered exactly once."""
