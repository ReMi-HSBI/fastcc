"""Framework for MQTT communication.

FastCC is a lightweight, efficient and developer-friendly framework for
`MQTT <https://mqtt.org>`_ communication. It is built on top of the
`aiomqtt <https://github.com/empicano/aiomqtt>`_ library and extends it
with the following functionalities:

+----------------------------------+---------------+
| Feature                          | Status        |
+==================================+===============+
| Request/Response                 | 📋 Planned    |
+----------------------------------+---------------+
| Streaming                        | 📋 Planned    |
+----------------------------------+---------------+
| Custom payload encoding/decoding | 📋 Planned    |
+----------------------------------+---------------+
| Routing                          | 📋 Planned    |
+----------------------------------+---------------+
"""

from fastcc.client import (
    Client,
    PublishContext,
    RequestContext,
    StreamContext,
    SubscribeContext,
    UnsubscribeContext,
)
from fastcc.exceptions import FastCCError, MqttConnectionError, RequestError
from fastcc.qos import QoS
from fastcc.router import Router

__all__ = [
    "Client",
    "FastCCError",
    "MqttConnectionError",
    "PublishContext",
    "QoS",
    "RequestContext",
    "RequestError",
    "Router",
    "StreamContext",
    "SubscribeContext",
    "UnsubscribeContext",
]
