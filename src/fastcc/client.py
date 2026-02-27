"""Module defining the ``Client`` class."""

import asyncio
import datetime
import logging
import math
import types
import typing

import aiomqtt
import paho.mqtt.properties as paho_properties
import paho.mqtt.subscribeoptions as paho_subscribeoptions

from fastcc.codec import CodecRegistry
from fastcc.constants import (
    DEFAULT_MESSAGING_TIMEOUT,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
)
from fastcc.exceptions import FastCCError, MessagingError
from fastcc.qos import QoS
from fastcc.serialization import serialize

__all__ = ["Client"]

_logger = logging.getLogger(__name__)


class Client:
    """Asynchronous MQTT client.

    This client is based on ``aiomqtt.Client`` [3]_ but implements
    additional functionalities for requesting and streaming data using
    MQTTv5 response topics. It also extends the basic payload types
    supported by ``aiomqtt`` with custom encoders and decoders.

    Parameters
    ----------
    host
        IP address or DNS name of the MQTT-Broker to connect to.
    port
        Port number of the MQTT-Broker to connect to.
    codec_registry
        Optional codec registry used for payload serialization.
    kwargs
        Additional keyword arguments passed to ``aiomqtt.Client``.

    References
    ----------
    .. [3] https://github.com/empicano/aiomqtt
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

        # Ensure MQTTv5
        kwargs.update({"protocol": aiomqtt.ProtocolVersion.V5})

        self._client = aiomqtt.Client(host, port, **kwargs)

    @property
    def host(self) -> str:
        """IP address or DNS name of the MQTT-Broker connected to."""
        return self._host

    @property
    def port(self) -> int:
        """Port number of the MQTT-Broker connected to."""
        return self._port

    async def __aenter__(self) -> typing.Self:
        addr = (self._host, self._port)
        try:
            await self._client.__aenter__()
        except aiomqtt.MqttError as e:
            error_message = "Failed connecting to MQTT broker on %s:%d"
            _logger.exception(error_message, *addr)
            raise FastCCError(error_message, *addr) from e

        _logger.info("Connected to MQTT broker on %s:%d", *addr)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self._client.__aexit__(exc_type, exc_value, traceback)

    async def publish(  # noqa: PLR0913
        self,
        topic: str,
        packet: typing.Any = None,
        *,
        qos: QoS = QoS.AT_LEAST_ONCE,
        retain: bool = False,
        properties: paho_properties.Properties | None = None,
        timeout: datetime.timedelta | None = DEFAULT_MESSAGING_TIMEOUT,  # noqa: ASYNC109
    ) -> None:
        """Publish a packet to a topic.

        Parameters
        ----------
        topic
            Topic to publish the packet to.
        packet
            Packet to publish.
        qos
            QoS level to use for publishing the packet.
        retain
            Whether the packet should be retained by the broker.
        properties
            Properties to include with the publication.
        timeout
            Maximum time to wait for the publication. If ``None``, wait
            indefinitely.

        Raises
        ------
        MessagingError
            If the publish operation fails or times out.
        """
        serialized = serialize(packet, registry=self._codec_registry)
        try:
            # Use ``timeout=math.inf`` and rely on built-in timeout
            # handling using ``asyncio.timeout``.
            async with asyncio.timeout(_timedelta_as_timeout(timeout)):
                await self._client.publish(
                    topic,
                    serialized,
                    qos=qos,
                    retain=retain,
                    properties=properties,
                    timeout=math.inf,
                )

        except aiomqtt.MqttCodeError as e:
            error_message = (
                "Publish to topic=%r with qos=%d (%s), retain=%r failed "
                "with error code: %r"
            )
            error_info: tuple[typing.Any, ...]
            error_info = (topic, qos.value, qos.name, retain, e.rc)
            _logger.exception(error_message, *error_info)
            raise MessagingError(error_message, *error_info) from e

        except TimeoutError as e:
            assert timeout is not None  # noqa: S101
            error_message = (
                "Publish to topic=%r with qos=%d (%s), retain=%r timed "
                "out after %.2f seconds"
            )
            error_info = (
                topic,
                qos.value,
                qos.name,
                retain,
                timeout.total_seconds(),
            )
            _logger.exception(error_message, *error_info)
            raise MessagingError(error_message, *error_info) from e

        _logger.debug(
            "Published to topic=%r with qos=%d (%s), retain=%r: %r",
            topic,
            qos.value,
            qos.name,
            retain,
            serialized,
        )

    async def subscribe(
        self,
        topic: str,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
        options: paho_subscribeoptions.SubscribeOptions | None = None,
        properties: paho_properties.Properties | None = None,
        timeout: datetime.timedelta | None = DEFAULT_MESSAGING_TIMEOUT,  # noqa: ASYNC109
    ) -> None:
        """Subscribe to a topic.

        Parameters
        ----------
        topic
            Topic to subscribe to.
        qos
            QoS level to use for subscribing.
        options
            Options to include with the subscription.
        properties
            Properties to include with the subscription.
        timeout
            Maximum time to wait for the subscription. If ``None``, wait
            indefinitely.

        Raises
        ------
        MessagingError
            If subscribing to the topic failed or timed out.
        """
        if options is None:
            options = paho_subscribeoptions.SubscribeOptions()

        # Parameter ``qos`` takes precedence over ``options.qos`` if both
        # are set.
        options.QoS = qos.value

        try:
            # Use ``timeout=math.inf`` and rely on built-in timeout
            # handling using ``asyncio.timeout``.
            async with asyncio.timeout(_timedelta_as_timeout(timeout)):
                await self._client.subscribe(
                    topic,
                    options=options,
                    properties=properties,
                    timeout=math.inf,
                )
        except aiomqtt.MqttCodeError as e:
            error_message = (
                "Subscribe to topic=%r with qos=%d (%s), failed with "
                "error code: %r"
            )
            error_info: tuple[typing.Any, ...]
            error_info = (topic, qos.value, qos.name, e.rc)
            _logger.exception(error_message, *error_info)
            raise MessagingError(error_message, *error_info) from e
        except TimeoutError as e:
            assert timeout is not None  # noqa: S101
            error_message = (
                "Subscribe to topic=%r with qos=%d (%s), timed out "
                "after %.2f seconds"
            )
            error_info = (
                topic,
                qos.value,
                qos.name,
                timeout.total_seconds(),
            )
            _logger.exception(error_message, *error_info)
            raise MessagingError(error_message, *error_info) from e

        _logger.debug(
            "Subscribed to topic=%r with qos=%d (%s)",
            topic,
            qos.value,
            qos.name,
        )

    async def unsubscribe(
        self,
        topic: str,
        *,
        properties: paho_properties.Properties | None = None,
        timeout: datetime.timedelta | None = DEFAULT_MESSAGING_TIMEOUT,  # noqa: ASYNC109
    ) -> None:
        """Unsubscribe from a topic.

        Parameters
        ----------
        topic
            Topic to unsubscribe from.
        properties
            Properties to include with the unsubscription.
        timeout
            Maximum time to wait for the unsubscription. If ``None``, wait
            indefinitely.

        Raises
        ------
        MessagingError
            If unsubscribing to the topic failed or timed out.
        """
        try:
            # Use `timeout=math.inf` and rely on built-in timeout
            # handling using `asyncio.timeout`.
            async with asyncio.timeout(_timedelta_as_timeout(timeout)):
                await self._client.unsubscribe(
                    topic,
                    properties=properties,
                    timeout=math.inf,
                )
        except aiomqtt.MqttCodeError as e:
            error_message = (
                "Unsubscribe from topic=%r failed with error code: %r"
            )
            error_info: tuple[typing.Any, ...] = (topic, e.rc)
            _logger.exception(error_message, *error_info)
            raise MessagingError(error_message, *error_info) from e
        except TimeoutError as e:
            assert timeout is not None  # noqa: S101
            error_message = (
                "Unsubscribe from topic=%r timed out after %.2f seconds"
            )
            error_info = (topic, timeout.total_seconds())
            raise MessagingError(error_message, *error_info) from e

        _logger.debug("Unsubscribed from topic=%r", topic)


def _timedelta_as_timeout(td: datetime.timedelta | None) -> float | None:
    """Convert ``td`` to ``asyncio.timeout`` processable timeout value.

    Parameters
    ----------
    td
        Time delta to convert. If ``None``, will be treated as infinite
        timeout.

    Returns
    -------
    float | None
        Timeout value in seconds, or ``None`` for infinite timeout.
    """
    return td.total_seconds() if td is not None else None
