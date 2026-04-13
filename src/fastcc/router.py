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
    SINGLE_LEVEL_WILDCARD,
    STATUS_CODE_FAILURE,
    STATUS_CODE_SUCCESS,
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
    pattern
        The MQTT topic pattern for this route, which may include path
        parameters and a multi-level wildcard.
    handler
        The asynchronous function that will be called when a message is
        published to a topic matching ``pattern``.

    Attributes
    ----------
    topic
        The concrete (subscribable) MQTT topic for this route.
    regex
        The compiled regular expression pattern used for matching
        topics of incoming messages against this route.
    """

    pattern: dataclasses.InitVar[str]

    handler: Routable
    topic: str = dataclasses.field(init=False)
    regex: re.Pattern = dataclasses.field(init=False)

    def __post_init__(self, pattern: str) -> None:
        validate_pattern(pattern)
        object.__setattr__(self, "topic", pattern_to_topic(pattern))
        object.__setattr__(self, "regex", compile_pattern(pattern))

    async def __call__(
        self,
        data: bytes,
        **path_parameters: str,
    ) -> bytes | None:
        """Invoke the route's handler with the given data.

        Parameters
        ----------
        data
            The payload data to pass to the handler function.
        path_parameters
            Path parameters extracted from the topic, where keys are
            parameter names and values are the corresponding values
            from the topic.

        Returns
        -------
        bytes | None
            The result returned by the handler function, or ``None`` if
            the handler does not return a value.
        """
        return await self.handler(data, **path_parameters)

    def match(self, topic: str) -> re.Match[str] | None:
        """Match a given topic against this route's pattern.

        Parameters
        ----------
        topic
            The MQTT topic to match against this route's pattern.

        Returns
        -------
        re.Match[str] | None
            A match object if the topic matches this route's pattern,
            otherwise ``None``.
        """
        return self.regex.fullmatch(topic)


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
        topic = message.topic.value

        route, path_parameters = self.get(topic)
        if route is None:
            return

        response_topic = None
        correlation_id = None
        if message.properties is not None:
            response_topic = getattr(message.properties, "ResponseTopic", None)
            correlation_id = getattr(
                message.properties,
                "CorrelationData",
                None,
            )

        response_properties = paho_properties.Properties(
            paho_packettypes.PacketTypes.PUBLISH,
        )
        status_code = STATUS_CODE_SUCCESS

        # TODO(jb): Injectors
        try:
            result = await route(message.payload, **path_parameters)
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

        # TODO(jb): What if this publish fails?
        await client.publish(response_topic, result, context=context)


def validate_pattern(pattern: str) -> None:
    """Validate a topic pattern for correctness.

    This function checks that the given MQTT topic pattern is valid,
    ensuring that wildcards are used correctly and that path parameters
    are well-formed.

    Parameters
    ----------
    pattern
        The MQTT topic pattern to validate.

    Raises
    ------
    ValueError
        If the pattern is invalid.
    """
    if not pattern:
        error_message = "Topic pattern cannot be empty"
        raise ValueError(error_message)

    if SINGLE_LEVEL_WILDCARD in pattern:
        error_message = (
            f"Invalid topic pattern: Single-level wildcard"
            f"'{SINGLE_LEVEL_WILDCARD}' is not allowed in topic "
            f"patterns. Use path parameters (e.g. '{{param}}') "
            f"instead."
        )
        raise ValueError(error_message)

    segments = pattern.split(TOPIC_SEPARATOR)
    for i, segment in enumerate(segments):
        if MULTI_LEVEL_WILDCARD in segment:
            if segment != MULTI_LEVEL_WILDCARD:
                error_message = (
                    f"Invalid topic pattern: Multi-level wildcard "
                    f"'{MULTI_LEVEL_WILDCARD}' must occupy an entire "
                    f"topic segment (invalid segment: '{segment}')."
                )
                raise ValueError(error_message)
            if i != len(segments) - 1:
                error_message = (
                    f"Invalid topic pattern: Multi-level wildcard "
                    f"'{MULTI_LEVEL_WILDCARD}' must be the last "
                    f"segment in the pattern (invalid position: "
                    f"segment {i} of {len(segments)})."
                )
                raise ValueError(error_message)

        if "{" in segment or "}" in segment:
            if (match := re.fullmatch(PATH_PARAMETER_PATTERN, segment)) is None:
                error_message = (
                    f"Invalid topic pattern: Path parameters must "
                    f"occupy an entire topic segment and be "
                    f"well-formed (invalid segment: '{segment}')."
                )
                raise ValueError(error_message)

            path_parameter_name = match.group(1)
            if path_parameter_name[0].isdigit():
                error_message = (
                    f"Invalid topic pattern: Path parameter names must "
                    f"start with a letter or underscore (invalid "
                    f"segment: '{segment}')."
                )
                raise ValueError(error_message)


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
    # Replace path-parameter with regex equivalent
    pattern = re.sub(PATH_PARAMETER_PATTERN, r"(?P<\1>[^/]+)", pattern)

    # Replace multi-level wildcard with regex equivalent
    pattern = pattern.replace(MULTI_LEVEL_WILDCARD, r"(?P<wildcard>.*)")

    return re.compile(pattern)


def pattern_to_topic(pattern: str) -> str:
    """Convert a topic pattern with path parameters to a concrete topic.

    This function replaces path parameters in the given MQTT topic
    pattern with single-level wildcards (``+``), resulting in a
    concrete topic that can be subscribed to.

    Parameters
    ----------
    pattern
        The MQTT topic pattern containing path parameters
        (e.g. ``{param}``).

    Returns
    -------
    str
        A concrete MQTT topic with path parameters replaced by ``+``.
    """
    return re.sub(PATH_PARAMETER_PATTERN, SINGLE_LEVEL_WILDCARD, pattern)
