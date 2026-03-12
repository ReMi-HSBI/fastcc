"""Asynchronous client to connect and communicate with an MQTT broker."""

import dataclasses
import logging
import typing
import uuid

if typing.TYPE_CHECKING:
    import datetime
    import types

    import paho.mqtt.properties as paho_properties

import aiomqtt

from fastcc.constants import DEFAULT_MQTT_HOST, DEFAULT_MQTT_PORT
from fastcc.exceptions import MqttConnectionError

_logger = logging.getLogger(__name__)

__all__ = ["Client", "MessageContext", "PublishContext"]


@dataclasses.dataclass(slots=True, kw_only=True)
class MessageContext:
    """Context for a messaging operation.

    Attributes
    ----------
    properties
        Properties to include with the operation.
    timeout
        Maximum time to wait for the operation to finish.
        If ``None``, wait indefinitely.
    """

    properties: paho_properties.Properties | None = None
    timeout: datetime.timedelta | None = None


@dataclasses.dataclass(slots=True, kw_only=True)
class PublishContext(MessageContext):
    """Context for a publish operation."""


class Client:
    """Asynchronous client to connect and communicate with an MQTT broker.

    This client is built on top of the
    `aiomqtt.Client <https://github.com/empicano/aiomqtt>`_,
    providing additional functionality and convenience methods for
    common MQTT operations.

    Parameters
    ----------
    host
        IP address or DNS name of the MQTT-Broker to connect to.
    port
        Port number of the MQTT-Broker to connect to.
    **kwargs
        Keyword arguments to be passed to the underlying client.

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
        **kwargs: typing.Any,
    ) -> None:
        self._host = host
        self._port = port

        # Ensure the client has a unique id if none is provided
        if "identifier" not in kwargs:
            kwargs["identifier"] = uuid.uuid4().hex

        # Ensure MQTT v5.0
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
            _logger.debug(
                "Failed to connect to MQTT broker on %s:%d",
                self._host,
                self._port,
                exc_info=exc,
            )
            raise MqttConnectionError(self._host, self._port) from exc

        _logger.info(
            "Connected to MQTT broker on %s:%d",
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

    async def publish(
        self,
        topic: str,
        payload: object,
        *,
        context: PublishContext | None = None,
    ) -> None: ...
