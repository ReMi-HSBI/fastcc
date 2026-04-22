import asyncio
import logging
import re
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    import aiomqtt

    from fastcc.client import Client


import paho.mqtt.packettypes as paho_packettypes
import paho.mqtt.properties as paho_properties

from fastcc.client import PublishContext, SubscribeContext
from fastcc.constants import (
    PATH_PARAMETER_PATTERN,
    SINGLE_LEVEL_WILDCARD,
    STATUS_CODE_FAILURE,
    STATUS_CODE_SUCCESS,
    TOPIC_SEPARATOR,
)
from fastcc.qos import QoS
from fastcc.route import Routable, Route

_logger = logging.getLogger(__name__)


class Router:
    """MQTT topic router for registering and resolving handlers.

    A router maintains a registry of topic patterns mapped to
    asynchronous handler functions. Topics may include path parameters
    (e.g. `{param}`) and the multi-level wildcard `#`. An optional
    prefix is prepended to all registered topics, enabling hierarchical
    composition of routers.

    Parameters
    ----------
    prefix
        A topic prefix prepended to every route registered on this
        router. Defaults to an empty string (no prefix).

    Examples
    --------
    >>> router = Router(prefix="home/devices")
    >>> @router.route("{device_id}/status")
    ... async def on_status(device_id: str, data: bytes) -> None:
    ...     pass
    """

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix.rstrip(TOPIC_SEPARATOR)
        self._routes: set[Route] = set()
        self._injectors: dict[str, typing.Any] = {}

    @property
    def routes(self) -> set[Route]:
        """Get the set of registered routes in this router."""
        return self._routes

    def get(self, topic: str) -> tuple[Route | None, dict[str, str]]:
        """Resolve a topic to a registered route.

        Parameters
        ----------
        topic
            The MQTT topic to resolve.

        Returns
        -------
        tuple[Route | None, dict[str, str]]
            A tuple containing the matching route and path parameters if found,
            otherwise ``(None, {})``.
        """
        for route in self._routes:
            if (match := route.match(topic)) is not None:
                return route, match.groupdict()
        return None, {}

    def route(
        self,
        pattern: str,
        *,
        context: SubscribeContext | None = None,
    ) -> Callable[[Routable], Routable]:
        """Register a route handler for a given topic pattern.

        Parameters
        ----------
        pattern
            The MQTT topic pattern for the route.
        context
            The context to use for this route.

        Returns
        -------
        Callable[[Routable], Routable]
            A decorator that registers the decorated function as a
            handler for the specified pattern.
        """

        def decorator(func: Routable) -> Routable:
            if self._prefix:
                full_pattern = TOPIC_SEPARATOR.join((
                    self._prefix,
                    pattern.lstrip(TOPIC_SEPARATOR),
                ))
            else:
                full_pattern = pattern

            self._routes.add(Route(full_pattern, func, context=context))
            _logger.debug("Registered route: %s -> %s", full_pattern, func)
            return func

        return decorator

    async def serve(self, client: Client) -> None:
        """Start the router to handle incoming messages from the MQTT client.

        This method subscribes to all registered topic patterns and
        dispatches incoming messages to the appropriate handlers based
        on topic matching.

        Parameters
        ----------
        client
            The MQTT client to use for subscribing and receiving
            messages.
        """
        _validate_injectors(self._injectors, self._routes)

        for route in self._routes:
            topic = _pattern_to_topic(route.pattern)
            await client.subscribe(topic, context=route.context)

        tasks: set[asyncio.Task[bytes | None]] = set()
        try:
            async for message in client.iter_messages():
                t = asyncio.create_task(self.__handle_message(message, client))
                tasks.add(t)
                t.add_done_callback(tasks.discard)
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

    def add_injectors(self, **injectors: typing.Any) -> None:
        """Add injectors to the router.

        Injectors are values that can be injected into route handlers as
        additional keyword arguments. This method allows adding multiple
        injectors at once.

        Parameters
        ----------
        **injectors
            Key-value pairs where keys are injector names and values are
            the corresponding injector values.
        """
        self._injectors.update(injectors)

    def add_router(self, router: Router) -> None:
        """Add routes from another router into this router.

        This method allows composing routers hierarchically by adding
        all routes from another router into this one. The added router's
        prefix will be preserved.

        Parameters
        ----------
        router
            The other router whose routes should be added to this router.
        """
        for route in router.routes:
            self.route(route.pattern, context=route.context)(route.handler)

    async def __handle_message(
        self,
        message: aiomqtt.Message,
        client: Client,
    ) -> None:
        topic = message.topic.value

        response_topic = None
        correlation_id = None
        if message.properties is not None:
            response_topic = getattr(message.properties, "ResponseTopic", None)
            correlation_id = getattr(
                message.properties,
                "CorrelationData",
                None,
            )

        route, path_parameters = self.get(topic)
        if route is None:
            return

        injectors = {
            name: self._injectors.get(name) for name in route.injectors
        }

        response_properties = paho_properties.Properties(
            paho_packettypes.PacketTypes.PUBLISH,
        )
        status_code = STATUS_CODE_SUCCESS
        try:
            value = client.codec_registry.decode(
                message.payload,
                route.payload_type,
            )
            result = await route(
                value,
                **path_parameters,
                **injectors,
            )
        except Exception as exc:  # noqa: BLE001
            result = str(exc).encode()
            status_code = (
                exc.status_code
                if hasattr(exc, "status_code")
                else STATUS_CODE_FAILURE
            )

        if response_topic is None:
            if result is not None:
                _logger.warning(
                    "Handler returned a result but no response topic "
                    "was provided in the message properties; result "
                    "will be discarded (topic: %r)",
                    topic,
                )
            return

        if correlation_id is None:
            _logger.warning(
                "Malformed message: No correlation ID was provided in "
                "the message properties; response will be discarded "
                "(topic: %r)",
                topic,
            )
            return

        response_properties.CorrelationData = correlation_id
        response_properties.UserProperty = [
            ("status_code", str(status_code)),
        ]
        context = PublishContext(
            _properties=response_properties,
            qos=QoS.AT_LEAST_ONCE,
        )

        await client.publish(response_topic, result, context=context)


def _pattern_to_topic(pattern: str) -> str:
    return re.sub(PATH_PARAMETER_PATTERN, SINGLE_LEVEL_WILDCARD, pattern)


def _validate_injectors(
    injectors: dict[str, typing.Any],
    routes: set[Route],
) -> None:
    required_injectors: set[str] = set()
    for route in routes:
        required_injectors.update(route.injectors)

    missing = required_injectors - injectors.keys()
    if missing:
        error_message = (
            f"Missing injectors: The following injectors are required "
            f"by registered routes but were not provided: {missing}"
        )
        raise ValueError(error_message)
