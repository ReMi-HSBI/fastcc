"""Module containing the `FastCC` application class."""

from __future__ import annotations

import asyncio
import inspect
import logging
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

    from fastcc.utilities.type_aliases import ExceptionHandler
    from fastcc.utilities.type_definitions import Packet

from google.protobuf.message import Message
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from fastcc.client import Client
from fastcc.exceptions import MQTTError
from fastcc.router import Router
from fastcc.utilities.analyze import extract_route_kwargs
from fastcc.utilities.mqtt import QoS, get_correlation_data, get_response_topic

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

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self._client = Client(*args, **kwargs)
        self._router = Router()
        self._injectors: dict[str, typing.Any] = {}
        self._exception_handlers: dict[type[Exception], ExceptionHandler] = {}
        self._exception_handlers.setdefault(MQTTError, lambda e: e)  # type: ignore [return-value, arg-type]

    async def run(self) -> None:
        """Start the application."""
        async with self._client:
            for topic, data in self._router.routes.items():
                for qos in data:
                    await self._client.subscribe(topic, qos=qos)

            await self.__listen()

    def add_router(self, router: Router) -> None:
        """Add a router to the app.

        Parameters
        ----------
        router
            Router to add.
        """
        self._router.add_router(router)

    def add_injector(self, **kwargs: typing.Any) -> None:
        """Add injector variables to the app.

        Injector variables are passed to the routables as keyword
        arguments if they are present (by name!).
        """
        self._injectors.update(kwargs)

    def add_exception_handler(
        self,
        exception_type: type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        """Register an exception handler.

        Parameters
        ----------
        exception_type
            Type of the exception to handle.
        handler
            Handler callable.
        """
        self._exception_handlers[exception_type] = handler

    async def __listen(self) -> None:
        _logger.info("Listen for incoming messages")
        async with asyncio.TaskGroup() as tg:
            async for message in self._client.messages:
                tg.create_task(self.__handle(message))

    async def __handle(self, message: aiomqtt.Message) -> None:
        topic = message.topic.value
        qos = QoS(message.qos)
        payload = message.payload

        _logger.debug(
            "Handle message on topic %r with qos=%d (%s): %r",
            topic,
            qos.value,
            qos.name,
            payload,
        )

        if not isinstance(payload, bytes):
            details = (
                f"Ignore message with unimplemented payload type "
                f"{type(payload).__name__!r}"
            )
            _logger.error(details)
            raise TypeError(details)

        # This should never happen, but just in case - dev's make mistakes.
        if (routings := self._router.routes.get(topic)) is None:
            details = f"Routings not found for message on topic {topic!r}"
            _logger.error(details)
            raise ValueError(details)

        # This should also never happen, but just in case - dev's make mistakes.
        if (routes := routings.get(qos)) is None:
            details = (
                f"Routes not found for message on topic {topic!r} "
                f"with qos={qos.value} ({qos.name})"
            )
            _logger.error(details)
            raise ValueError(details)

        for route in routes:
            properties = Properties(PacketTypes.PUBLISH)  # type: ignore [no-untyped-call]

            correlation_data = get_correlation_data(message)
            if correlation_data is not None:
                properties.CorrelationData = correlation_data

            response_topic = get_response_topic(message)
            kwargs = extract_route_kwargs(route, message, self._injectors)

            try:
                if inspect.isasyncgenfunction(route):
                    async for response in route(**kwargs):
                        await self.__send_response(
                            response,
                            response_topic,
                            qos,
                            properties,
                        )
                    await self.__send_response(
                        None,
                        response_topic,
                        qos,
                        properties,
                    )
                else:
                    response = await route(**kwargs)  # type: ignore [misc]
                    await self.__send_response(
                        response,
                        response_topic,
                        qos,
                        properties,
                    )
            except Exception as error:  # noqa: BLE001
                details = (
                    "Got %r while handling message on topic=%r with "
                    "payload_length=%d"
                )
                _logger.debug(details, error, topic, len(payload))

                response = repr(error)
                user_property = ("error", "None")

                exception_handler = self._exception_handlers.get(type(error))
                if exception_handler is not None:
                    mqtt_error = exception_handler(error)
                    response = mqtt_error.message
                    user_property = ("error", str(mqtt_error.error_code))

                properties.UserProperty = [user_property]

                await self.__send_response(
                    response,
                    response_topic,
                    qos,
                    properties,
                )

    async def __send_response(
        self,
        response: Packet | None,
        topic: str | None,
        qos: QoS,
        properties: Properties | None = None,
    ) -> None:
        if topic is None:
            return

        if isinstance(response, Message):
            response = response.SerializeToString()

        await self._client.publish(
            topic,
            response,
            qos=qos,
            properties=properties,
        )
