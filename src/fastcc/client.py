"""Module defining the ``Client`` class."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types
    import typing

import aiomqtt

from fastcc.constants import DEFAULT_MQTT_HOST, DEFAULT_MQTT_PORT
from fastcc.exceptions import FastCCError

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
        **kwargs: typing.Any,
    ) -> None:
        self._host = host
        self._port = port

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
