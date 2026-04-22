"""Asynchronous client to connect and communicate with an MQTT broker."""

import asyncio
import contextlib
import dataclasses
import logging
import math
import typing
import uuid

if typing.TYPE_CHECKING:
    import types
    from collections.abc import AsyncIterator

    from fastcc.codec_registry import CodecRegistry

import aiomqtt
import paho.mqtt.packettypes as paho_packettypes
import paho.mqtt.properties as paho_properties
import paho.mqtt.subscribeoptions as paho_subscribeoptions

from fastcc.codec_registry import default_codec_registry
from fastcc.constants import (
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
    DEFAULT_RESPONSE_TOPIC,
    TOPIC_SEPARATOR,
)
from fastcc.exceptions import FastCCError, MqttConnectionError
from fastcc.qos import QoS
from fastcc.response import Response
from fastcc.utilities import get_correlation_id

_logger = logging.getLogger(__name__)


class Client:
    """Asynchronous client to connect and communicate with an MQTT broker.

    This client is built on top of the
    `aiomqtt.Client <https://github.com/empicano/aiomqtt>`_, providing
    additional functionality and convenience methods for common MQTT
    operations.

    Parameters
    ----------
    host
        The IP address or DNS name of the MQTT-Broker to connect to.
    port
        The port number of the MQTT-Broker to connect to.
    response_topic
        The topic to listen for responses in request/response
        communication. The client id is automatically appended to the
        end of the topic to ensure uniqueness.
    codec_registry
        The codec registry to use for encoding and decoding messages.
        If ``None``, the default codec registry is used.
    **kwargs
        Additional keyword arguments are passed directly to the
        underlying ``aiomqtt.Client`` instance.

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
        *,
        response_topic: str = DEFAULT_RESPONSE_TOPIC,
        codec_registry: CodecRegistry | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._host = host
        self._port = port

        if codec_registry is None:
            codec_registry = default_codec_registry

        self._codec_registry = codec_registry

        # Ensure a unique client id is used (if none is provided)
        client_id = kwargs.get("identifier")
        if client_id is None:
            client_id = uuid.uuid4().hex
            kwargs["identifier"] = client_id

        assert isinstance(client_id, str), "Client identifier must be a string"

        self._response_topic = TOPIC_SEPARATOR.join((response_topic, client_id))

        # Ensure MQTTv5 is used no matter what the user specified
        kwargs["protocol"] = aiomqtt.ProtocolVersion.V5

        self._client = aiomqtt.Client(host, port, **kwargs)
        self._listener: asyncio.Task[None] | None = None
        self._messages: asyncio.Queue[aiomqtt.Message] = asyncio.Queue()
        self._pending_responses: dict[
            bytes,
            asyncio.Future[aiomqtt.Message],
        ] = {}
        self._pending_responses_queue: dict[
            bytes,
            asyncio.Queue[aiomqtt.Message],
        ] = {}

    async def __aenter__(self) -> typing.Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.stop(exc_type, exc_value, traceback)

    @property
    def host(self) -> str:
        """IP address or DNS name the client is or will be connected to."""
        return self._host

    @property
    def port(self) -> int:
        """Port number the client is or will be connected to."""
        return self._port

    @property
    def codec_registry(self) -> CodecRegistry:
        """The codec registry used for encoding and decoding messages."""
        return self._codec_registry

    async def connect(self) -> None:
        """Connect to the MQTT broker.

        This method just establishes a connection to the MQTT broker,
        but does not start listening for responses or incoming messages.

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


        Example
        -------
        >>> async def main() -> None:
        >>>    client = Client()
        >>>    try:
        >>>        await client.connect()
        >>>    finally:
        >>>        await client.disconnect()
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

    async def start(self) -> None:
        """Start the client.

        Connect to the MQTT broker and start listening for responses.

        Example
        -------
        >>> async def main() -> None:
        >>>    client = Client()
        >>>    try:
        >>>        await client.start()
        >>>    finally:
        >>>        await client.stop()

        Notes
        -----
        In almost any case, it is recommended to not call this method
        directly, but to use the asynchronous context manager instead.

        >>> async with Client() as client:
        ...     ...
        """
        await self.connect()
        self._listener = asyncio.create_task(self.__listen())

    async def stop(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: types.TracebackType | None = None,
    ) -> None:
        """Stop the client.

        Stop listening for responses and disconnect from the MQTT
        broker.

        Parameters
        ----------
        exc_type
            The exception type if ``stop`` was triggered by an
            exception, otherwise ``None``.
        exc_value
            The exception value if ``stop`` was triggered by an
            exception, otherwise ``None``.
        traceback
            The traceback if ``stop`` was triggered by an exception,
            otherwise ``None``.

        Notes
        -----
        In almost any case, it is recommended to not call this method
        directly, but to use the asynchronous context manager instead.

        >>> async with Client() as client:
        ...     ...
        """
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener

        await self.disconnect(exc_type, exc_value, traceback)

    async def publish(
        self,
        topic: str,
        value: typing.Any = None,
        *,
        context: PublishContext | None = None,
    ) -> None:
        """Publish ``value`` to the given ``topic``.

        The value is sent to the broker and then subsequently to any
        clients subscribing to matching topics.

        Parameters
        ----------
        topic
            The topic ``value`` should be published on.
        value
            The value to send. If ``None``, an empty payload is
            published. The value is tried to be converted by one of the
            registered codecs.
        context
            Context for the publish operation.

        Raises
        ------
        FastCCError
            If the publish operation fails.
        """
        payload = self._codec_registry.encode(value)

        if context is None:
            context = PublishContext()

        try:
            await self._client.publish(
                topic,
                payload,
                context.qos,
                context.retain,
                context.properties,
                timeout=math.inf,
            )
        except aiomqtt.MqttCodeError as exc:
            error_message = (
                f"Failed to publish to topic '{topic}' with QoS "
                f"{context.qos.value} ('{context.qos.name}')"
            )
            raise FastCCError(error_message) from exc

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
        FastCCError
            If the subscribe operation fails.
        """
        if context is None:
            context = SubscribeContext()

        try:
            await self._client.subscribe(
                topic,
                options=context.options,
                properties=context.properties,
                timeout=math.inf,
            )
        except aiomqtt.MqttCodeError as exc:
            error_message = (
                f"Failed to subscribe to topic '{topic}' with QoS "
                f"{context.qos.value} ('{context.qos.name}')"
            )
            raise FastCCError(error_message) from exc

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
        FastCCError
            If the unsubscribe operation fails.
        """
        if context is None:
            context = UnsubscribeContext()

        try:
            await self._client.unsubscribe(
                topic,
                context.properties,
                timeout=math.inf,
            )
        except aiomqtt.MqttCodeError as exc:
            error_message = f"Failed to unsubscribe from topic '{topic}'"
            raise FastCCError(error_message) from exc

        _logger.debug("Unsubscribed from topic '%s'", topic)

    async def request[T](
        self,
        topic: str,
        value: typing.Any = None,
        *,
        response_type: type[T],
        context: RequestContext | None = None,
    ) -> Response[T]:
        """Publish ``value`` and wait for the response.

        The value is sent to the broker and then subsequently to any
        clients subscribing to matching topics. Responses to the
        request are expected to be published by the responding client
        on the topic specified by the ``response_topic`` attribute of
        the request message, preserving the correlation ID.

        Parameters
        ----------
        topic
            The topic that ``value`` should be published on.
        value
            The value to send. If ``None``, an empty payload is
            published. The value is tried to be converted by one of the
            registered codecs.
        response_type
            The type to parse the response payload into.
        context
            Context for the request operation.

        Returns
        -------
        Response[T]
            The response to the request.
        """
        if context is None:
            context = RequestContext()

        cid = uuid.uuid4().bytes
        context.properties.CorrelationData = cid
        context.properties.ResponseTopic = self._response_topic

        response_future: asyncio.Future[aiomqtt.Message] = asyncio.Future()
        self._pending_responses[cid] = response_future

        try:
            await self.publish(topic, value, context=context)
            response_message = await response_future
            return Response.from_message(
                response_message,
                response_type,
                codec_registry=self._codec_registry,
            )
        finally:
            del self._pending_responses[cid]

    async def stream[T](
        self,
        topic: str,
        value: typing.Any = None,
        *,
        response_type: type[T],
        context: RequestContext | None = None,
    ) -> AsyncIterator[Response[T]]:
        """Publish ``value`` and stream the response.

        The stream ends when the responding client sends an empty
        response.

        Parameters
        ----------
        topic
            The topic that ``value`` should be published on.
        value
            The value to send. If ``None``, an empty payload is
            published. The value is tried to be converted by one of the
            registered codecs.
        response_type
            The type to parse the response payload into.
        context
            Context for the request operation.

        Yields
        ------
        Response[T]
            One response of the stream.
        """
        if context is None:
            context = StreamContext()

        cid = uuid.uuid4().bytes
        context.properties.CorrelationData = cid
        context.properties.ResponseTopic = self._response_topic

        response_queue: asyncio.Queue[aiomqtt.Message] = asyncio.Queue()
        self._pending_responses_queue[cid] = response_queue

        try:
            await self.publish(topic, value, context=context)
            while True:
                response_message = await response_queue.get()
                if response_message.payload == b"":
                    break

                yield Response.from_message(
                    response_message,
                    response_type,
                    codec_registry=self._codec_registry,
                )
        finally:
            del self._pending_responses_queue[cid]

    async def iter_messages(self) -> AsyncIterator[aiomqtt.Message]:
        """Iterate over incoming messages.

        This method yields messages received from the broker. The
        messages are yielded in the order they are received. Responses
        to requests or stream operations are excluded.

        Yields
        ------
        aiomqtt.Message
            An incoming message.
        """
        while True:
            yield await self._messages.get()

    async def __listen(self) -> None:
        options = paho_subscribeoptions.SubscribeOptions(
            qos=QoS.AT_LEAST_ONCE.value,
            noLocal=True,
        )
        context = SubscribeContext(_options=options)
        await self.subscribe(self._response_topic, context=context)
        try:
            _logger.info("Started listening")
            async for message in self._client.messages:
                if message.topic.value != self._response_topic:
                    await self._messages.put(message)
                    continue

                try:
                    cid = get_correlation_id(message)
                except AttributeError:
                    _logger.warning(
                        "Received response message without correlation "
                        "ID - ignoring message",
                    )
                    continue

                if cid in self._pending_responses:
                    response_future = self._pending_responses[cid]
                    response_future.set_result(message)
                elif cid in self._pending_responses_queue:
                    response_queue = self._pending_responses_queue[cid]
                    response_queue.put_nowait(message)
                else:
                    _logger.warning(
                        "Received response message with correlation ID "
                        "'%s', but no pending response was found for "
                        "this ID - ignoring message",
                        cid,
                    )

        finally:
            await self.unsubscribe(self._response_topic)
            _logger.info("Stopped listening")


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class MessageContext:
    """Context for a messaging operation.

    Parameters
    ----------
    _properties
        The properties to include with the messaging operation.

    Attributes
    ----------
    properties
        The properties to include with the messaging operation.
    """

    _properties: dataclasses.InitVar[paho_properties.Properties | None] = None

    properties: paho_properties.Properties = dataclasses.field(init=False)

    def __post_init__(
        self,
        _properties: paho_properties.Properties | None,
    ) -> None:
        self.properties = (
            paho_properties.Properties(
                paho_packettypes.PacketTypes.PUBLISH,
            )
            if _properties is None
            else _properties
        )


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
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


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class SubscribeContext(MessageContext):
    """Context for a subscribe operation.

    Parameters
    ----------
    _qos
        The quality of service level to use for subscribing.
        Use this parameter to shorthandly specify the QoS level for
        the subscription without having to create a full
        ``_options`` object. If the ``_options`` parameter is
        also specified, the QoS level from the ``_qos`` parameter
        takes precedence over the QoS level specified in the
        ``_options`` parameter.
    _options
        The options to include with the subscription.

    Attributes
    ----------
    options
        The options that are included with the subscription.
    """

    _qos: dataclasses.InitVar[QoS | None] = None
    _options: dataclasses.InitVar[
        paho_subscribeoptions.SubscribeOptions | None
    ] = None

    options: paho_subscribeoptions.SubscribeOptions = dataclasses.field(
        init=False,
        default_factory=paho_subscribeoptions.SubscribeOptions,
    )

    def __post_init__(
        self,
        _properties: paho_properties.Properties | None,
        _qos: QoS | None,
        _options: paho_subscribeoptions.SubscribeOptions | None,
    ) -> None:
        super().__post_init__(_properties)

        if _options is not None:
            self.options = _options

        qos = QoS.AT_MOST_ONCE if _qos is None else _qos
        self.options.QoS = qos.value

    @property
    def qos(self) -> QoS:
        """The quality of service level for the subscription."""
        return QoS(self.options.QoS)

    @qos.setter
    def qos(self, value: QoS) -> None:
        """Set the quality of service level for the subscription."""
        self.options.QoS = value.value


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class UnsubscribeContext(MessageContext):
    """Context for a unsubscribe operation."""


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class RequestContext(PublishContext):
    """Context for a request operation."""

    qos: QoS = QoS.AT_LEAST_ONCE

    def __post_init__(
        self,
        _properties: paho_properties.Properties | None,
    ) -> None:
        super().__post_init__(_properties)

        if self.qos == QoS.AT_MOST_ONCE:
            error_message = (
                f"QoS level for a request operation cannot be "
                f"{self.qos.value} ({self.qos.name})"
            )
            raise ValueError(error_message)

        if self.properties.packetType != paho_packettypes.PacketTypes.PUBLISH:
            error_message = (
                "Properties for a request operation must be of type PUBLISH"
            )
            raise ValueError(error_message)

        if hasattr(self.properties, "CorrelationData"):
            error_message = (
                "CorrelationData should not be set in the request "
                "context properties"
            )
            raise ValueError(error_message)

        if hasattr(self.properties, "ResponseTopic"):
            error_message = (
                "ResponseTopic should not be set in the request "
                "context properties"
            )
            raise ValueError(error_message)


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class StreamContext(RequestContext):
    """Context for a stream operation."""
