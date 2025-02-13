"""Module containing the `Client` class."""

from __future__ import annotations

import asyncio
import logging
import math
import typing
import uuid

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastcc.utilities.type_definitions import Packet

import aiomqtt
from google.protobuf.message import Message
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.subscribeoptions import SubscribeOptions

from fastcc.utilities.interpretation import bytes_to_packet
from fastcc.utilities.mqtt import QoS, check_error_code, verify_correlation_data

_logger = logging.getLogger(__name__)


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
        payload: Packet | None = None,
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
        payload
            Payload to publish.
            `None` will publish an empty message.
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
        RuntimeError
            If the publication fails.
        TimeoutError
            If the publication times out.
        """
        # `aiomqtt` uses `math.inf` instead of `None` to wait indefinitely.
        if timeout is None:
            timeout = math.inf

        if isinstance(payload, Message):
            payload = payload.SerializeToString()

        try:
            await super().publish(
                topic,
                payload,
                qos.value,
                retain,
                properties,
                timeout=timeout,
            )
        except aiomqtt.MqttCodeError as e:
            details = (
                f"Publish to topic={topic!r} with "
                f"qos={qos.value} [{qos.name}] failed with "
                f"error_code={e.rc}"
            )
            _logger.error(details)
            raise RuntimeError(details) from e
        except aiomqtt.MqttError as e:
            details = (
                f"Publish to topic={topic!r} with "
                f"qos={qos.value} [{qos.name}] timed out"
            )
            _logger.error(details)
            raise TimeoutError(details) from e

        details = "Published to topic=%r with qos=%d [%s], retain=%r: %r"
        _logger.debug(details, topic, qos.value, qos.name, retain, payload)

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
        RuntimeError
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
            details = (
                f"Subscribe to topic={topic!r} with "
                f"qos={qos.value} [{qos.name}] failed with "
                f"error_code={e.rc}"
            )
            _logger.error(details)
            raise RuntimeError(details) from e
        except aiomqtt.MqttError as e:
            details = (
                f"Subscribe to topic={topic!r} with "
                f"qos={qos.value} [{qos.name}] timed out"
            )
            _logger.error(details)
            raise TimeoutError(details) from e

        details = "Subscribed to topic=%r with qos=%d [%s]"
        _logger.debug(details, topic, qos.value, qos.name)

    async def unsubscribe(  # type: ignore [override]
        self,
        topic: str,
        *,
        properties: Properties | None = None,
        timeout: float | None = None,
    ) -> None:
        """Unsubscribe from a topic on the MQTT broker.

        Parameters
        ----------
        topic
            Topic to unsubscribe from.
        properties
            Properties to include with the unsubscription.
        timeout
            Time to wait for the unsubscription to finish in seconds.
            `None` will wait indefinitely.

        Raises
        ------
        RuntimeError
            If the unsubscription fails.
        TimeoutError
            If the unsubscription times out.
        """
        # `aiomqtt` uses `math.inf` instead of `None` to wait indefinitely.
        if timeout is None:
            timeout = math.inf

        try:
            await super().unsubscribe(topic, properties, timeout=timeout)
        except aiomqtt.MqttCodeError as e:
            details = (
                f"Unsubscribe from topic={topic!r} failed with "
                f"error_code={e.rc}"
            )
            _logger.error(details)
            raise RuntimeError(details) from e
        except aiomqtt.MqttError as e:
            details = f"Unsubscribe from topic={topic!r} timed out"
            _logger.error(details)
            raise TimeoutError(details) from e

        _logger.debug("Unsubscribed topic=%r", topic)

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
        ValueError
            If the properties are invalid.

        Returns
        -------
        Packet
            Response packet.
        """
        if pub_properties is None:
            pub_properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

        if pub_properties.packetType != PacketTypes.PUBLISH:
            details = (
                f"Publish properties must have packet type "
                f"{PacketTypes.PUBLISH} [PUBLISH] not "
                f"{pub_properties.packetType}"
            )
            _logger.error(details)
            raise ValueError(details)

        if getattr(pub_properties, "ResponseTopic", None) is not None:
            details = (
                "Setting the response topic on publish properties is "
                "not permitted"
            )
            _logger.error(details)
            raise ValueError(details)

        # Create a unique topic for the request to identify the response.
        response_topic = f"{self._response_topic_prefix}/{uuid.uuid4()}"

        # Set the response-topic as a property for the request.
        pub_properties.ResponseTopic = response_topic

        # Create a unique correlation-data id to make the request more secure.
        correlation_data = str(uuid.uuid4()).encode()

        # Set the correlation-data as a property for the request.
        pub_properties.CorrelationData = correlation_data

        # Subscribe to the response-topic before publishing to not miss
        # the response.
        await self.subscribe(
            response_topic,
            qos=qos,
            properties=sub_properties,
            timeout=sub_timeout,
        )

        try:
            await self.publish(
                topic,
                packet,
                qos=qos,
                retain=retain,
                properties=pub_properties,
                timeout=pub_timeout,
            )

            async with asyncio.timeout(response_timeout):
                return await self.__response(
                    response_topic,
                    correlation_data,
                    response_type,
                )
        except TimeoutError:
            _logger.error("Response on topic=%r timed out", response_topic)
            raise

        finally:
            await self.unsubscribe(response_topic)

    async def stream[T: Packet](  # noqa: PLR0913
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
    ) -> AsyncIterator[T]:
        """Request stream data from the MQTT broker.

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
        ValueError
            If the properties are invalid.

        Yields
        ------
        Packet
            Response packet.
        """
        if pub_properties is None:
            pub_properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

        if pub_properties.packetType != PacketTypes.PUBLISH:
            details = (
                f"Publish properties must have packet type "
                f"{PacketTypes.PUBLISH} [PUBLISH] not "
                f"{pub_properties.packetType}"
            )
            _logger.error(details)
            raise ValueError(details)

        if getattr(pub_properties, "ResponseTopic", None) is not None:
            details = (
                "Setting the response topic on publish properties is "
                "not permitted"
            )
            _logger.error(details)
            raise ValueError(details)

        # Create a unique topic for the request to identify the response.
        response_topic = f"{self._response_topic_prefix}/{uuid.uuid4()}"

        # Set the response-topic as a property for the request.
        pub_properties.ResponseTopic = response_topic

        # Create a unique correlation-data id to make the request more secure.
        correlation_data = str(uuid.uuid4()).encode()

        # Set the correlation-data as a property for the request.
        pub_properties.CorrelationData = correlation_data

        # Subscribe to the response-topic before publishing to not miss
        # the response.
        await self.subscribe(
            response_topic,
            qos=qos,
            properties=sub_properties,
            timeout=sub_timeout,
        )

        try:
            await self.publish(
                topic,
                packet,
                qos=qos,
                retain=retain,
                properties=pub_properties,
                timeout=pub_timeout,
            )

            async with asyncio.timeout(response_timeout):
                async for response in self.__stream_response(
                    response_topic,
                    correlation_data,
                    response_type,
                ):
                    yield response
        except TimeoutError:
            _logger.error("Response on topic=%r timed out", response_topic)
            raise

        finally:
            await self.unsubscribe(response_topic)

    async def __response[T: Packet](  # type: ignore [return]
        self,
        response_topic: str,
        correlation_data: bytes,
        response_type: type[T],
    ) -> T:
        try:
            async for message in self.messages:
                payload = message.payload
                assert isinstance(payload, bytes)  # noqa: S101

                if message.topic.matches(response_topic):
                    if verify_correlation_data(message, correlation_data):
                        check_error_code(message)
                        return bytes_to_packet(payload, response_type)

                await self._queue.put(message)

                # Wait a bit to not overload the CPU if the message is
                # the only one in the queue.
                if self._queue.qsize() == 1:
                    await asyncio.sleep(0.1)

        except aiomqtt.MqttError:
            details = "Disconnected during response message iteration"
            _logger.error(details)
            raise ConnectionAbortedError(details) from None

    async def __stream_response[T: Packet](
        self,
        response_topic: str,
        correlation_data: bytes,
        response_type: type[T],
    ) -> AsyncIterator[T]:
        try:
            async for message in self.messages:
                payload = message.payload
                assert isinstance(payload, bytes)  # noqa: S101

                if message.topic.matches(response_topic):
                    if verify_correlation_data(message, correlation_data):
                        check_error_code(message)

                        if payload == b"":
                            return

                        yield bytes_to_packet(payload, response_type)
                        continue

                await self._queue.put(message)

                # Wait a bit to not overload the CPU if the message is
                # the only one in the queue.
                if self._queue.qsize() == 1:
                    await asyncio.sleep(0.1)

        except aiomqtt.MqttError:
            details = "Disconnected during response message iteration"
            _logger.error(details)
            raise ConnectionAbortedError(details) from None
