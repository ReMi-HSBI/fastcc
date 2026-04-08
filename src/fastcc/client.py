"""Asynchronous client to connect and communicate with an MQTT broker."""

import asyncio
import contextlib
import logging
import typing
import uuid

if typing.TYPE_CHECKING:
    import types

import aiomqtt

from fastcc.exceptions import MqttConnectionError

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

    Notes
    -----
    The client relies on features introduced in version 5.0 of the MQTT
    protocol and will enforce the use of MQTT v5.0 when connecting to a
    broker.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1883,
        **kwargs: typing.Any,
    ) -> None:
        self._host = host
        self._port = port

        # Ensure a unique client id is used (if none is provided)
        client_id = kwargs.get("identifier")
        if client_id is None:
            client_id = uuid.uuid4().hex
            kwargs["identifier"] = client_id

        assert isinstance(client_id, str), "Client identifier must be a string"

        # Ensure MQTTv5 is used no matter what the user specified
        kwargs["protocol"] = aiomqtt.ProtocolVersion.V5

        self._client = aiomqtt.Client(host, port, **kwargs)
        self._listener: asyncio.Task[None] | None = None

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

    async def __listen(self) -> None:
        _logger.info("Started listening")
        # TODO(jb): Implement listening
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            _logger.info("Stopped listening")
