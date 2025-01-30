"""
Framework for component communication.

FastCC is a lightweight, efficient and developer-friendly framework for
component communication. By leveraging MQTT [1]_ for messaging and
Protocol Buffers [2]_ for data serialization, this framework ensures
fast, reliable, and bandwidth-efficient communication. Its simplicity
in setup and development makes it ideal for both small-scale and
enterprise-level applications.

References
----------
.. [1] https://mqtt.org
.. [2] https://protobuf.dev/
"""

from __future__ import annotations

import inspect
import logging
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from fastcc.utilities.type_aliases import Routable

import aiomqtt

from fastcc.utilities import interpretation
from fastcc.utilities.mqtt import QoS
from fastcc.utilities.validation import validate_route

__all__ = ["CCRouter", "FastCC"]

_logger = logging.getLogger(__name__)


class CCRouter:
    """Router for communication endpoints."""

    def __init__(self) -> None:
        self._routes: dict[str, dict[int, list[Routable]]] = {}

    @property
    def routes(self) -> dict[str, dict[int, list[Routable]]]:
        """Return all registered routes.

        Returns
        -------
        dict[str, dict[int, list[Routable]]]
            All registered routes.
        """
        return self._routes

    def route(
        self,
        topic: str,
        *,
        qos: QoS = QoS.AT_MOST_ONCE,
    ) -> Callable[[Routable], Routable]:
        """Register a (MQTT-) route.

        Parameters
        ----------
        topic
            MQTT topic to subscribe and assign the function to.
        qos
            Quality of Service level for the subscription.

        Returns
        -------
        Callable[[Routable], Routable]
            Decorated callable.
        """

        def decorator(routable: Routable) -> Routable:
            validate_route(routable)

            if topic not in self._routes:
                self._routes[topic] = {}

            if qos not in self._routes[topic]:
                self._routes[topic][qos] = []

            self._routes[topic][qos].append(routable)

            return routable

        return decorator

    def add_router(self, router: CCRouter) -> None:
        """Add another router to this router.

        Parameters
        ----------
        router
            Router to add.
        """
        self._routes.update(router.routes)


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

    def __init__(self, client: aiomqtt.Client) -> None:
        if client._client.protocol != aiomqtt.ProtocolVersion.V5:  # noqa: SLF001
            details = "client must support MQTT version 5.0"
            _logger.error(details)
            raise ValueError(details)

        self._client = client
        self._router = CCRouter()
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
                await self._client.subscribe(topic, qos)

        await self.__listen()

    def add_router(self, router: CCRouter) -> None:
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

    async def __handle(self, message: aiomqtt.Message) -> None:
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

            await callback(**kwargs)
