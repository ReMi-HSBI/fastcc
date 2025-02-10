"""Module containing the `Client` class."""

from __future__ import annotations

import asyncio
import contextlib
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

from fastcc.exceptions import MQTTError
from fastcc.utilities.interpretation import bytes_to_packet
from fastcc.utilities.mqtt import QoS

_logger = logging.getLogger(__name__)

_MAX_COLLISIONS = 10


class Client(aiomqtt.Client):
    """Client to nicely communicate with `FastCC` applications.

    This class is a wrapper around `aiomqtt.Client`.

    Parameters
    ----------
    args
        Positional arguments to pass to the MQTT client.
    response_topic_prefix
        Prefix for the response topics.
    kwargs
        Keyword arguments to pass to the MQTT client.
    """

    def __init__(
        self,
        *args: typing.Any,  # noqa: ANN401
        response_topic_prefix: str = "fastcc/responses",
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> None:
        self._response_topic_prefix = response_topic_prefix.rstrip("/")

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
        response_topic = f"{self._response_topic_prefix}/{uuid.uuid4()}"

        # Set the response-topic as a property for the request.
        pub_properties.ResponseTopic = response_topic

        # Create a unique correlation-data id to make the request more secure.
        correlation_data = str(uuid.uuid4()).encode()

        # Set the correlation-data as a property for the request.
        pub_properties.CorrelationData = correlation_data

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
                response = await self.__response(
                    response_topic,
                    correlation_data,
                    response_type,
                )
                _logger.debug("#request: got response on %r", response_topic)
                return response
        except TimeoutError:
            _logger.error(
                "#request: response on topic %r timed out",
                response_topic,
            )
            raise

    async def __response[T: Packet](  # noqa: C901
        self,
        response_topic: str,
        correlation_data: bytes,
        response_type: type[T],
    ) -> T:
        collisions = 0
        try:
            async for message in self.messages:
                if message.topic.matches(response_topic):
                    message_correlation_data = getattr(
                        message.properties,
                        "CorrelationData",
                        None,
                    )
                    if message_correlation_data is None:
                        details = (
                            "#request: invalid response on topic %r: "
                            "no correlation data - ignore (hacking attempt?)"
                        )
                        _logger.warning(details, response_topic)
                        continue

                    if message_correlation_data != correlation_data:
                        # Probably a response-topic collision, which is
                        # unlikely, but possible => put the message back
                        _logger.debug(
                            "#request: response collision on %r",
                            response_topic,
                        )

                        await self._queue.put(message)

                        if collisions > _MAX_COLLISIONS:
                            details = (
                                f"#request: too many collisions for "
                                f"response-topic {response_topic!r}"
                            )
                            _logger.error(details)
                            raise ValueError(details)

                        # Wait a bit to not overload the CPU if the message
                        # is the only one in the queue.
                        if self._queue.qsize() == 1:
                            await asyncio.sleep(0.1)

                        continue

                    if not isinstance(message.payload, bytes):
                        details = (
                            f"#request: message payload has unimplemented "
                            f"type {type(message.payload)}"
                        )
                        _logger.error(details)
                        raise NotImplementedError(details)

                    # Check for thrown errors
                    message_user_properties = getattr(
                        message.properties,
                        "UserProperty",
                        [],
                    )
                    with contextlib.suppress(StopIteration):
                        error_user_property: tuple[str, str] = next(
                            p
                            for p in message_user_properties
                            if p[0] == "error"
                        )
                        details = message.payload.decode()
                        _logger.error(details)

                        error_code_or_name = error_user_property[1]
                        if not error_code_or_name.isdigit():
                            raise ValueError(details)

                        raise MQTTError(details, int(error_code_or_name))

                    return bytes_to_packet(message.payload, response_type)

                await self._queue.put(message)

                # Wait a bit to not overload the CPU if the message is
                # the only one in the queue.
                if self._queue.qsize() == 1:
                    await asyncio.sleep(0.1)

        except aiomqtt.MqttError:
            details = "#request: disconnected during response message iteration"
            _logger.error(details)

            raise ConnectionAbortedError(details) from None

        details = f"#request: no response on topic {response_topic!r}"
        _logger.error(details)
        raise ValueError(details)
