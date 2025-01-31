"""Module containing the `FastCC` application class."""

from __future__ import annotations

import inspect
import logging
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

    from fastcc.client import Client

from google.protobuf.message import Message
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from fastcc.router import Router
from fastcc.utilities import interpretation
from fastcc.utilities.mqtt import QoS

_logger = logging.getLogger(__name__)


class FastCC:
    """Application class of FastCC.

    Parameters
    ----------
    client
        MQTT client instance.

    Raises
    ------
    ValueError
        If `client` does not support MQTT version 5.0.
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._router = Router()
        self._injectors: dict[str, typing.Any] = {}

    async def run(self) -> None:
        """Start the application.

        Raises
        ------
        ValueError
            If the initialized MQTT client is not connected.
        """
        if not self._client._connected.done():  # noqa: SLF001
            details = "client is not connected"
            _logger.error(details)
            raise ValueError(details)

        for topic, data in self._router.routes.items():
            for qos in data:
                _logger.info("Subscribing to topic %s (QoS %d)", topic, qos)
                await self._client.subscribe(topic, qos=QoS(qos))

        await self.__listen()

    def add_router(self, router: Router) -> None:
        """Add a router to the app.

        Parameters
        ----------
        router
            Router to add.
        """
        self._router.add_router(router)

    def add_injector(self, **kwargs: typing.Any) -> None:  # noqa: ANN401
        """Add injector variables to the app.

        Injector variables are passed to the routables as keyword
        arguments if they are present (by name!).
        """
        self._injectors.update(kwargs)

    async def __listen(self) -> None:
        async for message in self._client.messages:
            await self.__handle(message)

    async def __handle(self, message: aiomqtt.Message) -> None:  # noqa: C901
        if not isinstance(message.payload, bytes):
            details = (
                f"message type was expected to be bytes but was "
                f"{type(message.payload)}"
            )
            _logger.error(details)
            raise TypeError(details)

        if (routings := self._router.routes.get(message.topic.value)) is None:
            return

        if (callbacks := routings.get(QoS(message.qos))) is None:
            return

        for callback in callbacks:
            signature = inspect.signature(callback, eval_str=True)

            kwargs = {
                key: value
                for key, value in self._injectors.items()
                if key in signature.parameters
            }

            packet_parameter = interpretation.get_packet_parameter(callback)
            if packet_parameter is not None:
                packet = interpretation.bytes_to_packet(
                    message.payload,
                    packet_parameter.annotation,
                )
                kwargs[packet_parameter.name] = packet

            response = None
            properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]
            try:
                response = await callback(**kwargs)
            except Exception as error:
                response = str(error)
                properties.UserProperty = [("error", error.__class__.__name__)]
                _logger.exception("error while handling message")

            response_topic = getattr(message.properties, "ResponseTopic", None)

            if response_topic is not None:
                if isinstance(response, Message):
                    response = response.SerializeToString()

                await self._client.publish(
                    response_topic,
                    response,
                    qos=QoS(message.qos),
                    properties=properties,
                )
