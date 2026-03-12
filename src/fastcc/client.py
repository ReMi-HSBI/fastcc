"""Asynchronous client to connect and communicate with an MQTT broker."""

import logging
import typing
import uuid

if typing.TYPE_CHECKING:
    import types

import aiomqtt

from fastcc.constants import DEFAULT_MQTT_HOST, DEFAULT_MQTT_PORT
from fastcc.exceptions import MqttConnectionError

_logger = logging.getLogger(__name__)


class Client:
    """Asynchronous client to connect and communicate with an MQTT broker.

    This client is built on top of the ``aiomqtt.Client`` [1]_ ,
    providing additional functionality and convenience methods for
    common MQTT operations.

    Notes
    -----
    The client relies on features introduced in version 5.0 of the MQTT
    protocol and will enforce the use of MQTT v5.0 when connecting to a
    broker.

    References
    ----------
    .. [1] https://github.com/empicano/aiomqtt
    """

    def __init__(
        self,
        host: str = DEFAULT_MQTT_HOST,
        port: int = DEFAULT_MQTT_PORT,
        **kwargs: typing.Any,
    ) -> None:
        """Initialize the MQTT client.

        The constructor accepts all keyword arguments that are supported
        by the underlying ``aiomqtt.Client``.

        Parameters
        ----------
        host
            IP address or DNS name of the MQTT-Broker to connect to.
        port
            Port number of the MQTT-Broker to connect to.
        **kwargs
            Keyword arguments to be passed to the underlying client.
        """
        self._host = host
        self._port = port

        # Ensure the client has a unique id if none is provided
        if "identifier" not in kwargs:
            kwargs["identifier"] = uuid.uuid4().hex

        # Ensure MQTT v5.0
        kwargs["protocol"] = aiomqtt.ProtocolVersion.V5

        self._client = aiomqtt.Client(host, port, **kwargs)

    async def __aenter__(self) -> typing.Self:
        try:
            await self._client.__aenter__()
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
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self._client.__aexit__(exc_type, exc_value, traceback)

    @property
    def host(self) -> str:
        """IP address or DNS name the client is or will be connected to."""
        return self._host

    @property
    def port(self) -> int:
        """Port number the client is or will be connected to."""
        return self._port
