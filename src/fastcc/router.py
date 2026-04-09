import asyncio
import dataclasses
import logging
import re
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import aiomqtt

    from fastcc.client import Client

import paho.mqtt.packettypes as paho_packettypes
import paho.mqtt.properties as paho_properties

from fastcc.client import PublishContext
from fastcc.constants import (
    MULTI_LEVEL_WILDCARD,
    PATH_PARAMETER_PATTERN,
    TOPIC_SEPARATOR,
)
from fastcc.qos import QoS

_logger = logging.getLogger(__name__)

type Routable = Callable[..., Awaitable[bytes | None]]


@dataclasses.dataclass(frozen=True, match_args=False, slots=True)
class Route:
    """Represents a registered route in the MQTT topic router.

    A route consists of a topic pattern and an associated handler function.
    The topic pattern may include path parameters (e.g. `{param}`) and
    the multi-level wildcard `#`.

    Parameters
    ----------
    raw_pattern
        The MQTT topic pattern for this route, which may include path
        parameters and wildcards.
    handler
        The asynchronous function that will be called when a message is
        published to a topic matching this route's pattern.

    Attributes
    ----------
    topic
        The concrete (subscribable) topic for this route.
    pattern
        The compiled regular expression pattern used for matching topics
        against this route.
    """

    raw_pattern: dataclasses.InitVar[str]
    handler: Routable

    topic: str = dataclasses.field(init=False)
    pattern: re.Pattern = dataclasses.field(init=False)

    def __post_init__(self, raw_pattern: str) -> None:
        object.__setattr__(
            self,
            "topic",
            re.sub(r"\{[^}/]+\}", "+", raw_pattern),
        )
        object.__setattr__(self, "pattern", compile_pattern(raw_pattern))

    async def __call__(self, topic: str, data: bytes) -> bytes | None:
        """Invoke the route's handler with the given data.

        Parameters
        ----------
        topic
            The MQTT topic of the incoming message.
        data
            The payload data to pass to the handler function.

        Returns
        -------
        bytes | None
            The result returned by the handler function, or ``None`` if
            the handler does not return a value.
        """
        match = self.pattern.fullmatch(topic)
        if not match:
            return None  # TODO(jb)

        path_parameters = match.groupdict()
        return await self.handler(data, **path_parameters)


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

    @property
    def routes(self) -> set[Route]:
        """Get the set of registered routes in this router."""
        return self._routes

    def get(self, topic: str) -> Route | None:
        """Resolve a topic to a registered route.

        Parameters
        ----------
        topic
            The MQTT topic to resolve.

        Returns
        -------
        Route | None
            The matching route if found, otherwise ``None``.
        """
        for route in self._routes:
            if route.pattern.fullmatch(topic) is not None:
                return route
        return None

    def route(self, pattern: str) -> Callable[[Routable], Routable]:
        """Register a route handler for a given topic pattern.

        Parameters
        ----------
        pattern
            The MQTT topic pattern for the route.

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

            self._routes.add(Route(full_pattern, func))
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
        for route in self._routes:
            await client.subscribe(route.topic)

        tasks: set[asyncio.Task[bytes | None]] = set()
        try:
            async for message in client.iter_messages():
                t = asyncio.create_task(self.__handle_message(message, client))
                tasks.add(t)
                t.add_done_callback(tasks.discard)
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def __handle_message(
        self,
        message: aiomqtt.Message,
        client: Client,
    ) -> None:
        """Execute the handler for a given route with the provided topic and data.

        Parameters
        ----------
        message
            The incoming MQTT message.
        client
            The MQTT client, used for publishing responses.
        """
        topic = message.topic.value
        route = self.get(topic)
        if route is None:
            return

        result = await route(topic, message.payload)
        if result is None:
            return

        if message.properties is None:
            _logger.error("No properties for response")  # TODO(jb)
            return

        response_topic = getattr(message.properties, "ResponseTopic", None)
        if response_topic is None:
            _logger.error("No ResponseTopic for response")  # TODO(jb)
            return

        correlation_id = getattr(message.properties, "CorrelationData", None)
        if correlation_id is None:
            _logger.error("No CorrelationData for response")  # TODO(jb)
            return

        properties = paho_properties.Properties(
            paho_packettypes.PacketTypes.PUBLISH,
        )
        properties.CorrelationData = correlation_id
        context = PublishContext(_properties=properties, qos=QoS.AT_LEAST_ONCE)
        await client.publish(response_topic, result, context=context)


def compile_pattern(pattern: str) -> re.Pattern:
    """Compile a topic pattern string into a regular expression.

    This function converts MQTT topic patterns with path parameters and
    wildcards into regular expressions for matching.

    Parameters
    ----------
    pattern
        The MQTT topic pattern to compile, which may include path
        parameters (e.g. ``{param}``) and the multi-level wildcard
        ``#``.

    Returns
    -------
    re.Pattern
        A compiled regular expression that can be used to match topics
        against the given pattern.
    """
    escaped = re.escape(pattern)

    # Replace escaped parameter syntax with regex groups
    pattern = re.sub(PATH_PARAMETER_PATTERN, r"(?P<\1>[^/]+)", escaped)

    # Replace escaped multi-level wildcard with regex equivalent.
    pattern = pattern.replace(rf"\{MULTI_LEVEL_WILDCARD}", "(?P<wildcard>.+)")

    return re.compile(pattern)
