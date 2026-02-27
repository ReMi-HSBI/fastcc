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

from fastcc.client import Client
from fastcc.codec import CodecRegistry
from fastcc.constants import (
    DEFAULT_MESSAGING_TIMEOUT,
    DEFAULT_MQTT_HOST,
    DEFAULT_MQTT_PORT,
)
from fastcc.exceptions import FastCCError, MessagingError
from fastcc.qos import QoS
from fastcc.router import Router
from fastcc.serialization import deserialize

__all__ = ["Application"]

_logger = logging.getLogger(__name__)


class Application(Client):
    """Asynchronous MQTT application.

    This application is based on ``fastcc.Client`` [3]_ but implements
    additional functionalities for automatic message handling.

    References
    ----------
    .. [3] https://github.com/empicano/aiomqtt
    """

    def __init__(self, **kwargs: typing.Any) -> None:
        self._router = Router()
        self._injectors: dict[str, typing.Any] = {}
        super().__init__(**kwargs)

    def add_router(self, router: Router) -> None:
        """Add another router to this application.

        Parameters
        ----------
        router
            Router to add.
        """
        self._router.add_router(router)

    def add_injectors(self, **injectors: typing.Any) -> None:
        """Add injectors to this application.

        Parameters
        ----------
        **injectors
            Injectors to add, specified as keyword arguments where the
            key is the name of the injector and the value is the
            injector itself.
        """
        self._injectors.update(injectors)

    async def run(self) -> None:
        """Run the application."""
        self._validate_injectors()
        await self._subscribe_to_registered_routes()

        _logger.info("Application started")
        try:
            await self._listen()
        finally:
            _logger.info("Application shut down")

    def _validate_injectors(self) -> None:
        """Validate that the application has all injectors required by the registered routes.

        Raises
        ------
        FastCCError
            If any registered route requires an injector that is not provided by the application.
        """  # noqa: E501
        for route in self._router.routes:
            missing = route.expected_injector_names - self._injectors.keys()
            if missing:
                names = ", ".join(missing)
                error_message = (
                    f"Application is missing injector(s) for route on "
                    f"topic {route.topic!r}: {names}"
                )
                _logger.error(error_message)
                raise FastCCError(error_message)

    async def _subscribe_to_registered_routes(self) -> None:
        """Subscribe to all topics of the registered routes."""
        for route in self._router.routes:
            await self.subscribe(
                route.topic,
                qos=route.qos,
                options=route.options,
                properties=route.properties,
                timeout=route.timeout,
            )

    async def _listen(self) -> None:
        """Listen for incoming messages and dispatch them to the appropriate route handlers."""  # noqa: E501
        async for message in self._client.messages:
            packet = deserialize(message.payload, registry=self._codec_registry)
            response = await self._router.dispatch(
                message.topic.value,
                packet,
                **self._injectors,
            )

            if response is None:
                continue

            print(response)
