"""Asynchronous client to connect and communicate with an MQTT broker."""

import asyncio
import dataclasses
import logging
import typing
import uuid

if typing.TYPE_CHECKING:
    import datetime
    import types

    import paho.mqtt.properties as paho_properties
    import paho.mqtt.subscribeoptions as paho_subscribeoptions

    from fastcc.codec import CodecRegistry

import aiomqtt

from fastcc.constants import DEFAULT_MQTT_HOST, DEFAULT_MQTT_PORT
from fastcc.exceptions import (
    MqttConnectionError,
    OperationError,
    OperationTimeoutError,
)
from fastcc.qos import QoS
from fastcc.serialization import serialize

_logger = logging.getLogger(__name__)

__all__ = [
    "Client",
    "MessageContext",
    "PublishContext",
    "SubscribeContext",
    "UnsubscribeContext",
]


@dataclasses.dataclass(slots=True, kw_only=True)
class MessageContext:
    """Context for a messaging operation.

    Parameters
    ----------
    properties
        The properties to include with the messaging operation.
    timeout
        The maximum time to wait for the messaging operation to finish.
        If ``None``, wait indefinitely.
    """

    properties: paho_properties.Properties | None = None
    timeout: datetime.timedelta | None = None


@dataclasses.dataclass(slots=True, kw_only=True)
class PublishContext(MessageContext):
    """Context for a publish operation.

    Attributes
    ----------
    qos
        The quality of service level to use for publishing.
    retain
        Whether the packet should be retained by the broker.
    """

    qos: QoS = QoS.AT_MOST_ONCE
    retain: bool = False


@dataclasses.dataclass(slots=True, kw_only=True)
class SubscribeContext(MessageContext):
    """Context for a subscribe operation.

    Attributes
    ----------
    qos
        The quality of service level for the subscription.
    options
        The options to include with the subscription.
    """

    qos: QoS = QoS.AT_MOST_ONCE
    options: paho_subscribeoptions.SubscribeOptions | None = None


@dataclasses.dataclass(slots=True, kw_only=True)
class UnsubscribeContext(MessageContext):
    """Context for a unsubscribe operation."""


class Client:
    """Asynchronous client to connect and communicate with an MQTT broker.

    This client is built on top of the
    `aiomqtt.Client <https://github.com/empicano/aiomqtt>`_,
    providing additional functionality and convenience methods for
    common MQTT operations.

    Parameters
    ----------
    host
        The IP address or DNS name of the MQTT-Broker to connect to.
    port
        The port number of the MQTT-Broker to connect to.
    **kwargs
        Additional keyword arguments to be passed to the underlying
        client.

    Notes
    -----
    The client relies on features introduced in version 5.0 of the MQTT
    protocol and will enforce the use of MQTT v5.0 when connecting to a
    broker.
    """

    def __init__(
        self,
        host: str = DEFAULT_MQTT_HOST,
        port: int = DEFAULT_MQTT_PORT,
        codec_registry: CodecRegistry | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._host = host
        self._port = port
        self._codec_registry = codec_registry

        # Ensure a unique identifier is set.
        if "identifier" not in kwargs:
            kwargs["identifier"] = uuid.uuid4().hex

        # Ensure MQTTv5 is used.
        kwargs["protocol"] = aiomqtt.ProtocolVersion.V5

        self._client = aiomqtt.Client(host, port, **kwargs)

    async def __aenter__(self) -> typing.Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.disconnect(exc_type, exc_value, traceback)

    @property
    def host(self) -> str:
        """IP address or DNS name the client is or will be connected to."""
        return self._host

    @property
    def port(self) -> int:
        """Port number the client is or will be connected to."""
        return self._port

    async def connect(self) -> None:
        """Connect to the MQTT broker.

        Example
        -------
        >>> async def main() -> None:
        >>>    client = Client()
        >>>    try:
        >>>        await client.connect()
        >>>    finally:
        >>>        await client.disconnect()

        Raises
        ------
        MqttConnectionError
            If the connection to the MQTT broker fails.

        Notes
        -----
        In almost any case, it is recommended to not call this method
        directly, but to use the asynchronous context manager instead.

        >>> async with Client() as client:
        ...     ...
        """
        try:
            await self._client.__aenter__()  # noqa: PLC2801
        except aiomqtt.MqttError as exc:
            raise MqttConnectionError(host=self._host, port=self._port) from exc

        _logger.info(
            "Connected to MQTT broker on '%s:%d'",
            self._host,
            self._port,
        )

    async def disconnect(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: types.TracebackType | None = None,
    ) -> None:
        """Disconnect from the MQTT broker.

        Parameters
        ----------
        exc_type
            The exception type if the disconnection is triggered by an
            exception, otherwise ``None``.
        exc_value
            The exception value if the disconnection is triggered by an
            exception, otherwise ``None``.
        traceback
            The traceback if the disconnection is triggered by an
            exception, otherwise ``None``.

        Notes
        -----
        In almost any case, it is recommended to not call this method
        directly, but to use the asynchronous context manager instead.

        >>> async with Client() as client:
        ...     ...
        """
        await self._client.__aexit__(exc_type, exc_value, traceback)

        _logger.info(
            "Disconnected from MQTT broker on '%s:%d'",
            self._host,
            self._port,
        )

    async def publish(
        self,
        topic: str,
        value: typing.Any = None,
        *,
        context: PublishContext | None = None,
    ) -> None:
        """Publish a packet.

        The packet is sent to the broker and then subsequently to any
        clients subscribing to matching topics.

        Parameters
        ----------
        topic
            The topic that the packet should be published on.
        value
            The actual value to send.
            If ``None``, an empty value is published.
        context
            Context for the publish operation.

        Raises
        ------
        OperationError
            If the publish operation fails.
        OperationTimeoutError
            If the publish operation times out.
        """
        if context is None:
            context = PublishContext()

        payload = serialize(value, self._codec_registry)
        timeout = _timedelta_to_seconds(context.timeout)
        try:
            async with asyncio.timeout(timeout):
                await self._client.publish(
                    topic,
                    payload,
                    context.qos,
                    context.retain,
                    context.properties,
                )
        except aiomqtt.MqttCodeError as exc:
            raise OperationError(operation="publish", topic=topic) from exc
        except TimeoutError as exc:
            assert timeout is not None  # noqa: S101
            raise OperationTimeoutError(
                operation="publish",
                topic=topic,
                timeout=timeout,
            ) from exc

        _logger.debug(
            "Published to topic '%s' with QoS %d ('%s')",
            topic,
            context.qos.value,
            context.qos.name,
        )

    async def subscribe(
        self,
        topic: str,
        *,
        context: SubscribeContext | None = None,
    ) -> None:
        """Subscribe to a topic.

        Parameters
        ----------
        topic
            The topic to subscribe to.
        context
            Context for the subscribe operation.

        Raises
        ------
        OperationError
            If the subscribe operation fails.
        OperationTimeoutError
            If the subscribe operation times out.
        """
        if context is None:
            context = SubscribeContext()

        timeout = _timedelta_to_seconds(context.timeout)
        try:
            async with asyncio.timeout(timeout):
                await self._client.subscribe(
                    topic,
                    context.qos,
                    context.options,
                    context.properties,
                )
        except aiomqtt.MqttCodeError as exc:
            raise OperationError(operation="subscribe", topic=topic) from exc
        except TimeoutError as exc:
            assert timeout is not None  # noqa: S101
            raise OperationTimeoutError(
                operation="subscribe",
                topic=topic,
                timeout=timeout,
            ) from exc

        _logger.debug(
            "Subscribed to topic '%s' with QoS %d ('%s')",
            topic,
            context.qos.value,
            context.qos.name,
        )

    async def unsubscribe(
        self,
        topic: str,
        *,
        context: UnsubscribeContext | None = None,
    ) -> None:
        """Unsubscribe from a topic.

        Parameters
        ----------
        topic
            The topic to unsubscribe from.
        context
            The context for the unsubscribe operation.

        Raises
        ------
        OperationError
            If the unsubscribe operation fails.
        OperationTimeoutError
            If the unsubscribe operation times out.
        """
        if context is None:
            context = UnsubscribeContext()

        timeout = _timedelta_to_seconds(context.timeout)
        try:
            async with asyncio.timeout(timeout):
                await self._client.unsubscribe(topic, context.properties)
        except aiomqtt.MqttCodeError as exc:
            raise OperationError(operation="unsubscribe", topic=topic) from exc
        except TimeoutError as exc:
            assert timeout is not None  # noqa: S101
            raise OperationTimeoutError(
                operation="unsubscribe",
                topic=topic,
                timeout=timeout,
            ) from exc

        _logger.debug("Unsubscribed from topic '%s'", topic)


def _timedelta_to_seconds(timeout: datetime.timedelta | None) -> float | None:
    """Convert a timedelta object to seconds.

    Parameters
    ----------
    timeout
        The timedelta to convert.

    Returns
    -------
    float | None
        The equivalent duration in seconds.
        ``None`` if no timeout was specified.
    """
    return timeout.total_seconds() if timeout else None
