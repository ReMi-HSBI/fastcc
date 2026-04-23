"""Framework for MQTT communication.

FastCC is a lightweight, efficient and developer-friendly framework for
`MQTT <https://mqtt.org>`_ communication. It is built on top of the
`aiomqtt <https://github.com/empicano/aiomqtt>`_ library and extends it
with the following functionalities:

+----------------------------------+---------------+
| Feature                          | Status        |
+==================================+===============+
| Request/Response                 | ✅ Done       |
+----------------------------------+---------------+
| Streaming                        | ✅ Done       |
+----------------------------------+---------------+
| Routing                          | ✅ Done       |
+----------------------------------+---------------+
| Custom encoding/decoding         | ✅ Done       |
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
from fastcc.constants import STATUS_CODE_FAILURE, STATUS_CODE_SUCCESS
from fastcc.exceptions import FastCCError, MqttConnectionError, RequestError
from fastcc.qos import QoS
from fastcc.router import Routable, Router

__all__ = [
    "STATUS_CODE_FAILURE",
    "STATUS_CODE_SUCCESS",
    "Client",
    "FastCCError",
    "MqttConnectionError",
    "PublishContext",
    "QoS",
    "RequestContext",
    "RequestError",
    "Routable",
    "Router",
    "StreamContext",
    "SubscribeContext",
    "UnsubscribeContext",
]
