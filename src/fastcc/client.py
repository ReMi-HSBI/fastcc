"""Module containing the `Client` class."""

from __future__ import annotations

import asyncio
import logging
import math
import typing
import uuid

if typing.TYPE_CHECKING:
    from fastcc.utilities.type_definitions import Packet

import aiomqtt
from google.protobuf.message import Message
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.subscribeoptions import SubscribeOptions

from fastcc.utilities.interpretation import bytes_to_packet
from fastcc.utilities.mqtt import QoS

_logger = logging.getLogger(__name__)


class Client(aiomqtt.Client):
    """Client to nicely communicate with `FastCC` applications.

    This class is a wrapper around `aiomqtt.Client`.

    Parameters
    ----------
    args
        Positional arguments to pass to the MQTT client.
    kwargs
        Keyword arguments to pass to the MQTT client.
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:  # noqa: ANN401
        # Ensure that the MQTT client uses the MQTT v5 protocol.
        kwargs.update({"protocol": aiomqtt.ProtocolVersion.V5})

        super().__init__(*args, **kwargs)

    async def publish(  # type: ignore [override]  # noqa: PLR0913
        self,
        topic: str,
        packet: Packet | None = None,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
        retain: bool = False,
        properties: Properties | None = None,
        timeout: float | None = None,
    ) -> None:
        """Publish a message to the MQTT broker.

        Parameters
        ----------
        topic
            Topic to publish the message to.
        packet
            Packet to publish.
            `None` will publish an empty packet.
        qos
            Quality of service level.
        retain
            Whether to retain the packet.
        properties
            Properties to include with the packet.
        timeout
            Time to wait for the publication to finish in seconds.
            `None` will wait indefinitely.

        Raises
        ------
        ConnectionError
            If the publication fails.
        TimeoutError
            If the publication times out.
        """
        # `aiomqtt` uses `math.inf` instead of `None` to wait indefinitely.
        if timeout is None:
            timeout = math.inf

        if isinstance(packet, Message):
            packet = packet.SerializeToString()

        try:
            await super().publish(
                topic,
                packet,
                qos.value,
                retain,
                properties,
                timeout=timeout,
            )
        except aiomqtt.MqttCodeError as e:
            details = str(e)
            _logger.error(details)
            raise ConnectionError(details) from None
        except aiomqtt.MqttError as e:
            details = str(e)
            _logger.error(details)
            raise TimeoutError(details) from None

    async def subscribe(  # type: ignore [override]
        self,
        topic: str,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
        properties: Properties | None = None,
        timeout: float | None = None,
    ) -> None:
        """Subscribe to a topic on the MQTT broker.

        Parameters
        ----------
        topic
            Topic to subscribe to.
        qos
            Quality of service level.
        properties
            Properties to include with the subscription.
        timeout
            Time to wait for the subscription to finish in seconds.
            `None` will wait indefinitely.

        Raises
        ------
        ConnectionError
            If the subscription fails.
        TimeoutError
            If the subscription times out.
        """
        # `aiomqtt` uses `math.inf` instead of `None` to wait indefinitely.
        if timeout is None:
            timeout = math.inf

        try:
            await super().subscribe(
                topic,
                options=SubscribeOptions(qos=qos.value),
                properties=properties,
                timeout=timeout,
            )
        except aiomqtt.MqttCodeError as e:
            details = str(e)
            _logger.error(details)
            raise ConnectionError(details) from None
        except aiomqtt.MqttError as e:
            details = str(e)
            _logger.error(details)
            raise TimeoutError(details) from None

    async def request[T: Packet](  # noqa: PLR0913
        self,
        topic: str,
        packet: Packet | None,
        response_type: type[T],
        *,
        qos: QoS = QoS.EXACTLY_ONCE,
        retain: bool = False,
        sub_properties: Properties | None = None,
        sub_timeout: float | None = None,
        pub_properties: Properties | None = None,
        pub_timeout: float | None = None,
        response_timeout: float | None = None,
    ) -> T:
        """Send a request to the MQTT broker.

        Parameters
        ----------
        topic
            Topic to publish the request to.
        packet
            Packet to send with the request.
        response_type
            Type of the response packet.
        qos
            Quality of service level.
        retain
            Whether the request should be retained.
        sub_properties
            Properties for the subscription.
        sub_timeout
            Time to wait for the subscription to finish in seconds.
            `None` will wait indefinitely.
        pub_properties
            Properties for the publication.
        pub_timeout
            Time to wait for the publication to finish in seconds.
            `None` will wait indefinitely.
        response_timeout
            Time to wait for the response in seconds.
            `None` will wait indefinitely.

        Raises
        ------
        TimeoutError
            If the response times out.

        Returns
        -------
        Packet
            Response packet.
        """
        if sub_properties is None:
            sub_properties = Properties(PacketTypes.SUBSCRIBE)  # type: ignore [no-untyped-call]

        if pub_properties is None:
            pub_properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

        # Create a unique topic for the request to identify the response.
        response_topic = f"fastcc/responses/{uuid.uuid4()}"

        # Set the response-topic as a property for the request.
        pub_properties.ResponseTopic = response_topic

        _logger.debug(
            "#request: subscribe to topic %r with qos=%d (%s)",
            response_topic,
            qos.value,
            qos.name,
        )

        # Subscribe to the response-topic before publishing to not miss
        # the response.
        await self.subscribe(
            response_topic,
            qos=qos,
            properties=sub_properties,
            timeout=sub_timeout,
        )

        _logger.debug(
            "#request: publish to topic %r with qos=%d (%s): %r",
            topic,
            qos.value,
            qos.name,
            packet,
        )

        await self.publish(
            topic,
            packet,
            qos=qos,
            retain=retain,
            properties=pub_properties,
            timeout=pub_timeout,
        )

        _logger.debug(
            "#request: await response on topic %r with timeout=%r",
            response_topic,
            response_timeout,
        )

        try:
            async with asyncio.timeout(response_timeout):
                response = await self.__response(response_topic, response_type)
                _logger.debug("#request: got response on %r", response_topic)
                return response
        except TimeoutError:
            _logger.error(
                "#request: response on topic %r timed out",
                response_topic,
            )
            raise

    async def __response[T: Packet](
        self,
        topic: str,
        response_type: type[T],
    ) -> T:
        while True:
            message = await anext(self.messages)

            if not isinstance(message.payload, bytes):
                details = (
                    f"message payload has unimplemented type "
                    f"{type(message.payload)}"
                )
                _logger.error(details)
                raise NotImplementedError(details)

            # Not using `topic.matches()` here, as the response-topic
            # should be unique to the request. Therefore a normal string
            # comparison is sufficient (and faster).
            if message.topic.value != topic:
                # Put the message back into the messages-queue, as it
                # was not the response to the request.
                await self._queue.put(message)
                continue

            # Check for thrown errors on the responder-side.
            user_properties = getattr(message.properties, "UserProperty", [])
            user_property_keys = [i[0] for i in user_properties]
            if "error" in user_property_keys:
                details = message.payload.decode()
                _logger.error(details)
                raise ValueError(details)

            return bytes_to_packet(message.payload, response_type)
