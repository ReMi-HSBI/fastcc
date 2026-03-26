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
| Request/Response                 | ✅ Done       |
+----------------------------------+---------------+
| Streaming                        | ✅ Done       |
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
from fastcc.constants import STATUS_CODE_SUCCESS
from fastcc.qos import QoS
from fastcc.serialization import default_registry

__all__ = [
    "STATUS_CODE_SUCCESS",
    "Client",
    "PublishContext",
    "QoS",
    "RequestContext",
    "StreamContext",
    "SubscribeContext",
    "UnsubscribeContext",
    "default_registry",
]
