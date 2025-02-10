"""
Framework for component communication.

FastCC is a lightweight, efficient and developer-friendly framework for
component communication. By leveraging MQTT [1]_ for messaging and
Protocol Buffers [2]_ for data serialization, this framework ensures
fast, reliable, and bandwidth-efficient communication. Its simplicity
in setup and development makes it ideal for both small-scale and
enterprise-level applications.

References
----------
.. [1] https://mqtt.org
.. [2] https://protobuf.dev/
"""

from __future__ import annotations

__all__ = ["Client", "FastCC", "MQTTError", "Packet", "QoS", "Router"]

from .app import FastCC
from .client import Client
from .exceptions import MQTTError
from .router import Router
from .utilities.mqtt import QoS
from .utilities.type_definitions import Packet
