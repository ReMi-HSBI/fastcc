"""Module defining the ``Router`` class used for MQTT topic routing."""

import dataclasses
import datetime
import inspect
import re
import typing
from collections.abc import Awaitable, Callable

import paho.mqtt.properties as paho_properties
import paho.mqtt.subscribeoptions as paho_subscribeoptions

from fastcc.constants import (
    MULTI_LEVEL_WILDCARD,
    SINGLE_LEVEL_WILDCARD,
    TOPIC_SEPARATOR,
    WILDCARD_PARAMETER_NAME,
)
from fastcc.exceptions import FastCCError
from fastcc.qos import QoS

__all__ = ["Router"]
type _RouteHandler = Callable[..., Awaitable[typing.Any]]


@dataclasses.dataclass(frozen=True, slots=True)
class _Route:
    """Route metadata."""

    topic_pattern: str
    handler: _RouteHandler

    topic: str = dataclasses.field(init=False)
    regex: re.Pattern[str] = dataclasses.field(init=False)

    _: dataclasses.KW_ONLY

    qos: QoS = QoS.AT_MOST_ONCE
    options: paho_subscribeoptions.SubscribeOptions | None
    properties: paho_properties.Properties | None
    timeout: datetime.timedelta | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "topic",
            _topic_pattern_to_topic(self.topic_pattern),
        )
        object.__setattr__(
            self,
            "regex",
            _compile_topic_pattern(self.topic_pattern),
        )

        _validate_handler(self, self.handler)

    @property
    def expected_packet_parameter_name(self) -> str | None:
        """Name of the expected packet parameter for this route, or ``None`` if not expected."""  # noqa: E501
        signature = inspect.signature(self.handler)
        for parameter in signature.parameters.values():
            if (
                parameter.kind
                in {
                    parameter.POSITIONAL_OR_KEYWORD,
                    parameter.KEYWORD_ONLY,
                }
                and parameter.name not in self.expected_path_parameter_names
            ):
                return parameter.name
        return None

    @property
    def expected_path_parameter_names(self) -> set[str]:
        """Set of expected path parameter names for this route."""
        return set(self.regex.groupindex.keys())

    @property
    def expected_injector_names(self) -> set[str]:
        """Set of expected injector names for this route."""
        signature = inspect.signature(self.handler)
        return {
            p.name
            for p in signature.parameters.values()
            if p.kind == p.KEYWORD_ONLY
        } - self.expected_path_parameter_names


class Router:
    """MQTT topic router for dispatching messages to handlers based on topic patterns."""  # noqa: E501

    def __init__(self, prefix: str | None = None) -> None:
        self._prefix = prefix or ""
        self._routes: set[_Route] = set()

    def add_router(self, router: Router) -> None:
        """Add another router to this router.

        Parameters
        ----------
        router
            Router to add.
        """
        self._routes.update(router.routes)

    @property
    def routes(self) -> set[_Route]:
        """Set of registered routes."""
        return self._routes

    def route(
        self,
        topic_pattern: str,
        qos: QoS = QoS.AT_MOST_ONCE,
        options: paho_subscribeoptions.SubscribeOptions | None = None,
        properties: paho_properties.Properties | None = None,
        timeout: datetime.timedelta | None = None,
    ) -> Callable[[_RouteHandler], _RouteHandler]:
        """Register a handler for ``topic_pattern`` via decorator.

        Parameters
        ----------
        topic_pattern
            Topic pattern that may include named parameters like
            ``"{area_id}"``.
        qos
            Quality of Service level for this route.
        options
            MQTT subscribe options for this route.
        properties
            MQTT properties for this route.
        timeout
            Timeout for subscribing to this route.

        Returns
        -------
        typing.Callable[[_RouteHandler], _RouteHandler]
            Decorator registering the decorated handler in this router.
        """
        full_pattern = TOPIC_SEPARATOR.join((self._prefix, topic_pattern))

        def decorator(handler: _RouteHandler) -> _RouteHandler:
            route = _Route(
                topic_pattern=full_pattern,
                handler=handler,
                qos=qos,
                options=options,
                properties=properties,
                timeout=timeout,
            )
            self._routes.add(route)
            return handler

        return decorator

    async def dispatch(
        self,
        topic: str,
        packet: typing.Any = None,
        **injectors: typing.Any,
    ) -> typing.Any | None:
        """Dispatch ``packet`` to the first handler matching ``topic``.

        Parameters
        ----------
        topic
            Topic of the incoming message.
        packet
            Already-decoded message payload passed to the handler.
        **injectors
            Available application injectors to be passed to the handler.

        Returns
        -------
        typing.Any | None
            Return value of the matched handler, or ``None`` if no route
            matches.
        """
        for route in self._routes:
            match = route.regex.fullmatch(topic)
            if match is None:
                continue

            arguments: dict[str, typing.Any] = {}
            for parameter_name in route.expected_path_parameter_names:
                arguments[parameter_name] = match.group(parameter_name) or ""

            if route.expected_packet_parameter_name is not None:
                arguments[route.expected_packet_parameter_name] = packet

            # It is guaranteed by the application that all expected
            # injectors are available, so we can safely access them here.
            for injector_name in route.expected_injector_names:
                arguments[injector_name] = injectors[injector_name]

            return await route.handler(**arguments)

        return None


def _compile_topic_pattern(topic_pattern: str) -> re.Pattern[str]:  # noqa: C901, PLR0912
    """Compile ``topic_pattern`` into regex.

    Parameters
    ----------
    topic_pattern
        Topic pattern that may contain ``{param}`` placeholders.

    Returns
    -------
    re.Pattern[str]
        Compiled regex.

    Raises
    ------
    FastCCError
        If the topic pattern contains invalid placeholders.
    """
    parameter_names: list[str] = []
    regex_parts: list[str] = []

    segments = topic_pattern.split(TOPIC_SEPARATOR)

    if MULTI_LEVEL_WILDCARD in topic_pattern:
        if not topic_pattern.endswith(TOPIC_SEPARATOR + MULTI_LEVEL_WILDCARD):
            error_message = (
                "Invalid topic pattern; multi-level wildcard must be the "
                "last segment in topic: %r"
            )
            raise FastCCError(error_message, topic_pattern)
        has_wildcard = True

    for segment in segments:
        if not segment:
            regex_parts.append("")
            continue

        if segment.startswith("{") and segment.endswith("}"):
            parameter_name = segment[1:-1]
            if not parameter_name.isidentifier():
                error_message = (
                    "Invalid topic pattern; path-parameter in topic"
                    "pattern must be valid identifiers not %r"
                )
                raise FastCCError(error_message, parameter_name)
            if parameter_name == WILDCARD_PARAMETER_NAME:
                error_message = (
                    "Invalid topic pattern; path-parameter in topic"
                    "pattern cannot be named %r because it is reserved"
                )
                raise FastCCError(error_message, WILDCARD_PARAMETER_NAME)
            if parameter_name in parameter_names:
                error_message = (
                    "Invalid topic pattern; duplicate path-parameter in "
                    "topic pattern: %r"
                )
                raise FastCCError(error_message, parameter_name)

            parameter_names.append(parameter_name)
            regex_parts.append(f"(?P<{parameter_name}>[^{TOPIC_SEPARATOR}]+)")
            continue

        if "{" in segment or "}" in segment:
            error_message = (
                "Invalid topic pattern; invalid placeholder syntax in "
                "segment: %r"
            )
            raise FastCCError(error_message, segment)

        regex_parts.append(re.escape(segment))

    regex_pattern = "^" + TOPIC_SEPARATOR.join(regex_parts)
    if has_wildcard:
        if regex_parts and regex_parts != [""]:
            regex_pattern += (
                f"(?:{TOPIC_SEPARATOR}(?P<{WILDCARD_PARAMETER_NAME}>.*))?"
            )
        elif regex_parts == [""]:
            regex_pattern += (
                f"{TOPIC_SEPARATOR}(?P<{WILDCARD_PARAMETER_NAME}>.*)"
            )
        else:
            regex_pattern += f"(?P<{WILDCARD_PARAMETER_NAME}>.*)"

    regex_pattern += "$"
    return re.compile(regex_pattern)


def _topic_pattern_to_topic(topic_pattern: str) -> str:
    """Convert ``topic_pattern`` to MQTT topic by replacing placeholders with wildcards.

    Parameters
    ----------
    topic_pattern
        Topic pattern that may contain ``{param}`` placeholders.

    Returns
    -------
    str
        MQTT topic with placeholders replaced by single-level wildcards.
    """  # noqa: E501
    return re.sub(r"\{[^{}]+\}", SINGLE_LEVEL_WILDCARD, topic_pattern)


def _validate_handler(route: _Route, handler: _RouteHandler) -> None:
    """Validate handler signature.

    Parameters
    ----------
    route
        Route metadata.
    handler
        Async route handler.

    Raises
    ------
    FastCCError
        If the handler signature is incompatible with the route.
    """
    is_async_func = inspect.iscoroutinefunction(handler)
    if not is_async_func:
        error_message = "Handler %r for topic %r must be an async function"
        raise FastCCError(
            error_message,
            handler.__qualname__,
            route.topic_pattern,
        )

    # Validate that the handler has parameters for all expected path parameters
    signature = inspect.signature(handler)
    for parameter_name in route.expected_path_parameter_names:
        if parameter_name not in signature.parameters:
            error_message = (
                "Path parameter %r is missing in handler %r for topic %r"
            )
            raise FastCCError(
                error_message,
                parameter_name,
                handler.__qualname__,
                route.topic_pattern,
            )

    # Validate that the handler has only one non-path parameter, which
    # is expected to be the packet
    non_path_parameters = {
        p
        for p in signature.parameters.values()
        if p.name not in route.expected_path_parameter_names
        and p.kind
        in {
            p.POSITIONAL_OR_KEYWORD,
            p.KEYWORD_ONLY,
        }
    }
    if len(non_path_parameters) > 1:
        error_message = (
            "Handler %r for topic %r has more than one packet parameter: %r"
        )
        raise FastCCError(
            error_message,
            handler.__qualname__,
            route.topic_pattern,
            {p.name for p in non_path_parameters},
        )
