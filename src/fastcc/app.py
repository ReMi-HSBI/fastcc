"""Module containing the `FastCC` application class."""

from __future__ import annotations

import inspect
import logging
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

from google.protobuf.message import Message
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from fastcc.client import Client
from fastcc.router import Router
from fastcc.utilities import interpretation
from fastcc.utilities.mqtt import QoS

_logger = logging.getLogger(__name__)


class FastCC:
    """Application class of FastCC.

    Parameters
    ----------
    args
        Positional arguments to pass to the MQTT client.
    kwargs
        Keyword arguments to pass to the MQTT client.
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:  # noqa: ANN401
        self._client = Client(*args, **kwargs)
        self._router = Router()
        self._injectors: dict[str, typing.Any] = {}

    async def run(self) -> None:
        """Start the application."""
        async with self._client:
            for topic, data in self._router.routes.items():
                for qos in data:
                    await self._client.subscribe(topic, qos=qos)
                    _logger.info(
                        "subscribe to topic %r with qos=%d (%s)",
                        topic,
                        qos.value,
                        qos.name,
                    )

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
        _logger.info("listen for incoming messages")
        async for message in self._client.messages:
            await self.__handle(message)

    async def __handle(self, message: aiomqtt.Message) -> None:  # noqa: C901
        topic = message.topic.value
        qos = QoS(message.qos)
        payload = message.payload

        _logger.debug(
            "handle message on topic %r with qos=%d (%s): %r",
            topic,
            qos.value,
            qos.name,
            payload,
        )

        if not isinstance(payload, bytes):
            details = (
                f"ignore message with unimplemented payload type "
                f"{type(payload).__name__!r}"
            )
            _logger.error(details)
            raise TypeError(details)

        # This should never happen, but just in case - dev's make mistakes.
        if (routings := self._router.routes.get(topic)) is None:
            details = f"routings not found for message on topic {topic!r}"
            _logger.error(details)
            raise ValueError(details)

        # This should also never happen, but just in case - dev's make mistakes.
        if (routes := routings.get(qos)) is None:
            details = (
                f"routes not found for message on topic {topic!r} "
                f"with qos={qos.value} ({qos.name})"
            )
            _logger.error(details)
            raise ValueError(details)

        for route in routes:
            signature = inspect.signature(route, eval_str=True)

            kwargs = {
                key: value
                for key, value in self._injectors.items()
                if key in signature.parameters
            }

            packet_parameter = interpretation.get_packet_parameter(route)
            if packet_parameter is not None:
                packet = interpretation.bytes_to_packet(
                    payload,
                    packet_parameter.annotation,
                )
                kwargs[packet_parameter.name] = packet

            properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

            try:
                response = await route(**kwargs)
            except Exception as error:  # noqa: BLE001
                response = str(error)

                error_name = error.__class__.__name__
                properties.UserProperty = [("error", error_name)]

                _logger.error(
                    "got %r while handling message: %r",
                    error_name,
                    response,
                )

            response_topic = getattr(message.properties, "ResponseTopic", None)
            if response_topic is not None:
                if isinstance(response, Message):
                    response = response.SerializeToString()

                _logger.debug(
                    "publish response on topic %r with qos=%d (%s): %r",
                    response_topic,
                    qos.value,
                    qos.name,
                    response,
                )

                await self._client.publish(
                    response_topic,
                    response,
                    qos=qos,
                    properties=properties,
                )
