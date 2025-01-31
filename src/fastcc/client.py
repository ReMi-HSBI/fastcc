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

from fastcc.utilities.constants import MQTT_RESPONSE_TIMEOUT
from fastcc.utilities.interpretation import bytes_to_packet
from fastcc.utilities.mqtt import QoS

_logger = logging.getLogger(__name__)


class Client(aiomqtt.Client):
    """Client to nicely communicate with `FastCC` applications.

    This class is a wrapper around `aiomqtt.Client`.
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:  # noqa: ANN401
        # Ensure that the MQTT client uses the MQTT v5 protocol.
        kwargs.update({"protocol": aiomqtt.ProtocolVersion.V5})

        super().__init__(*args, **kwargs)

    async def publish(  # type: ignore [override]
        self,
        topic: str,
        message: Packet | None = None,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
        retain: bool = False,
        properties: Properties | None = None,
    ) -> None:
        """Publish a message to the MQTT broker.

        Parameters
        ----------
        topic
            Topic to publish the message to.
        message
            Message to publish.
        qos
            Quality of service level.
        retain
            Whether to retain the message.
        properties
            Properties to include with the message.
        """
        if isinstance(message, Message):
            message = message.SerializeToString()

        await super().publish(topic, message, qos.value, retain, properties)

    async def subscribe(  # type: ignore [override]
        self,
        topic: str,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
        properties: Properties | None = None,
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
        """
        await super().subscribe(
            topic,
            options=SubscribeOptions(qos=qos.value),
            properties=properties,
        )

    async def request(  # noqa: PLR0913
        self,
        topic: str,
        message: Packet | None,
        response_type: type[Packet],
        *,
        qos: QoS = QoS.EXACTLY_ONCE,
        retain: bool = False,
        sub_properties: Properties | None = None,
        sub_timeout: float | None = None,
        pub_properties: Properties | None = None,
        pub_timeout: float | None = None,
        response_timeout: float = MQTT_RESPONSE_TIMEOUT,
    ) -> Packet:
        """Send a request to the MQTT broker.

        Parameters
        ----------
        topic
            Topic to publish the request to.
        message
            Message to send with the request.
        response_type
            Type of the response message.
        qos
            Quality of service level.
        retain
            Whether the request should be retained.
        sub_properties
            Properties for the subscription.
        sub_timeout
            Time to wait for the subscription in seconds.
        pub_properties
            Properties for the publication.
        pub_timeout
            Time to wait for the publication in seconds.
        response_timeout
            Time to wait for the response in seconds.

        Raises
        ------
        TimeoutError
            If the response times out.

        Returns
        -------
        Packet
            Response message.
        """
        if sub_properties is None:
            sub_properties = Properties(PacketTypes.SUBSCRIBE)  # type: ignore [no-untyped-call]

        if sub_timeout is None:
            # aiomqtt use `math.inf` instead of `None` for infinite timeouts.
            sub_timeout = math.inf

        if pub_properties is None:
            pub_properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

        if pub_timeout is None:
            # aiomqtt use `math.inf` instead of `None` for infinite timeouts.
            pub_timeout = math.inf

        # Create a unique topic for the request to identify the response.
        response_topic = f"fastcc/responses/{uuid.uuid4()}"

        # Set the response-topic as a property for the request.
        pub_properties.ResponseTopic = response_topic

        # Subscribe to the response-topic before publishing to not miss the
        # response.
        try:
            async with asyncio.timeout(sub_timeout):
                await self.subscribe(
                    response_topic,
                    qos=qos,
                    properties=sub_properties,
                )
        except TimeoutError:
            details = f"Subscribe on topic={response_topic!r} timed out"
            _logger.error(details)
            raise

        details = (
            f"Publishing MQTT request to {topic=!r} with "
            f"response-topic={response_topic!r} and QoS={qos}"
        )
        _logger.debug(details)
        try:
            async with asyncio.timeout(pub_timeout):
                await self.publish(
                    topic,
                    message,
                    qos=qos,
                    retain=retain,
                    properties=pub_properties,
                )
        except TimeoutError:
            details = f"Publish on topic={response_topic!r} timed out"
            _logger.error(details)
            raise

        details = (
            f"Awaiting MQTT response on topic={response_topic!r} with "
            f"timeout={response_timeout}"
        )
        _logger.debug(details)
        try:
            async with asyncio.timeout(response_timeout):
                response = await self.__response(
                    response_topic,
                    response_type=response_type,
                )
                details = f"Received MQTT response on topic={response_topic!r}"
                _logger.debug(details)
                return response
        except TimeoutError:
            details = f"Response on topic={response_topic!r} timed out"
            _logger.error(details)
            raise

    async def __response(
        self,
        topic: str,
        *,
        response_type: type[Packet],
    ) -> Packet:
        while True:
            message = await anext(self.messages)

            if not isinstance(message.payload, bytes):
                details = "Message has invalid payload - continue."
                _logger.debug(details)
                continue

            # Not using `topic.matches()` here, as the response-topic should
            # be unique to the request. Therefore a normal string comparison
            # is sufficient (and faster).
            if message.topic.value != topic:
                # Put the message back into the messages-queue, as it was
                # not the response to the request.
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
