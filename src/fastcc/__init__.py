"""Framework for MQTT communication.

FastCC is a lightweight, efficient and developer-friendly framework for
`MQTT <https://mqtt.org>`_ communication. It is built on top of the
`aiomqtt <https://github.com/empicano/aiomqtt>`_ library and extends it
with the following functionalities:

+----------------------------------+---------------+
| Feature                          | Status        |
+==================================+===============+
| Routing                          | 📋 Planned    |
+----------------------------------+---------------+
| Custom payload encoding/decoding | ✅ Done       |
+----------------------------------+---------------+
| Request/Response                 | 📋 Planned    |
+----------------------------------+---------------+
| Streaming                        | 📋 Planned    |
+----------------------------------+---------------+
"""

from fastcc.client import (
    Client,
    PublishContext,
    SubscribeContext,
    UnsubscribeContext,
)
from fastcc.qos import QoS
from fastcc.serialization import default_registry

__all__ = [
    "Client",
    "PublishContext",
    "QoS",
    "SubscribeContext",
    "UnsubscribeContext",
    "default_registry",
]
