"""Framework for MQTT communication.

FastCC is a lightweight, efficient and developer-friendly framework for
MQTT [1]_ communication. It is built on top of the **aiomqtt** [2]_
library and extends it with the following functionalities:

+----------------------------------+---------------+
| Feature                          | Status        |
+==================================+===============+
| Routing                          | 📋Planned     |
+----------------------------------+---------------+
| Custom payload encoding/decoding | ✅Implemented |
+----------------------------------+---------------+
| Request/Response                 | 📋Planned     |
+----------------------------------+---------------+
| Streaming                        | 📋Planned     |
+----------------------------------+---------------+

References
----------
.. [1] https://mqtt.org
.. [2] https://github.com/empicano/aiomqtt
"""

from fastcc.app import Application
from fastcc.client import Client
from fastcc.codec import Codec, CodecRegistry
from fastcc.router import Router
from fastcc.serialization import default_registry

__all__ = [
    "Application",
    "Client",
    "Codec",
    "CodecRegistry",
    "Router",
    "default_registry",
]
