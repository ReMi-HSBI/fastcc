"""Module defining the ``Router`` class used for MQTT topic routing."""

import dataclasses
import datetime
import inspect
import logging
import re
import typing
from collections.abc import Callable

import paho.mqtt.properties as paho_properties
import paho.mqtt.subscribeoptions as paho_subscribeoptions

from fastcc.annotations import AnyCallable, RouteHandler
from fastcc.constants import (
    MULTI_LEVEL_WILDCARD,
    PATH_PARAMETER_PATTERN,
    SINGLE_LEVEL_WILDCARD,
    TOPIC_SEPARATOR,
    WILDCARD_PARAMETER_NAME,
)
from fastcc.exceptions import RouteValidationError
from fastcc.qos import QoS

__all__ = ["Router"]


_logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class _Route:
    """Route metadata."""

    topic_pattern: str
    handler: RouteHandler

    topic: str = dataclasses.field(init=False)
    regex: re.Pattern[str] = dataclasses.field(init=False)

    _: dataclasses.KW_ONLY

    qos: QoS = QoS.AT_MOST_ONCE
    options: paho_subscribeoptions.SubscribeOptions | None
    properties: paho_properties.Properties | None
    timeout: datetime.timedelta | None

    packet_parameter: str | None = dataclasses.field(init=False)
    path_parameters: frozenset[str] = dataclasses.field(init=False)
    injector_parameters: frozenset[str] = dataclasses.field(init=False)

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
        object.__setattr__(
            self,
            "path_parameters",
            frozenset(self.regex.groupindex.keys()),
        )
        object.__setattr__(
            self,
            "injector_parameters",
            frozenset(self._get_injector_parameters()),
        )
        object.__setattr__(
            self,
            "packet_parameter",
            self._get_packet_parameter(),
        )

    def _get_injector_parameters(self) -> set[str]:
        signature = inspect.signature(self.handler)
        return {
            p.name
            for p in signature.parameters.values()
            if p.kind == p.KEYWORD_ONLY
        } - self.path_parameters

    def _get_packet_parameter(self) -> str | None:
        signature = inspect.signature(self.handler)
        packet_parameters: list[str] = [
            p.name
            for p in signature.parameters.values()
            if p.kind
            in {
                p.POSITIONAL_OR_KEYWORD,
                p.KEYWORD_ONLY,
            }
            and p.name not in self.path_parameters
        ]
        if not packet_parameters:
            return None

        assert len(packet_parameters) == 1  # noqa: S101
        return packet_parameters[0]


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
    ) -> Callable[[AnyCallable], RouteHandler]:
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
        typing.Callable[[AnyCallable], RouteHandler]
            Decorator registering the decorated handler in this router.
        """
        full_pattern = TOPIC_SEPARATOR.join((self._prefix, topic_pattern))
        _validate_topic_pattern(full_pattern)

        def decorator(handler: AnyCallable) -> RouteHandler:
            _validate_route_handler(handler, full_pattern)
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
            for parameter_name in route.path_parameters:
                arguments[parameter_name] = match.group(parameter_name) or ""

            if route.packet_parameter is not None:
                arguments[route.packet_parameter] = packet

            # It is guaranteed by the application that all expected
            # injectors are available, so we can safely access them here.
            for injector_name in route.injector_parameters:
                arguments[injector_name] = injectors[injector_name]

            return await route.handler(**arguments)

        return None


def _validate_topic_pattern(topic_pattern: str) -> None:
    """Validate topic pattern.

    Parameters
    ----------
    topic_pattern
        Topic pattern to validate.

    Raises
    ------
    RouteValidationError
        If the topic pattern is invalid.
    """
    if not topic_pattern:
        error_message = "Invalid topic pattern; topic pattern cannot be empty"
        _logger.error(error_message)
        raise RouteValidationError(error_message)

    if SINGLE_LEVEL_WILDCARD in topic_pattern:
        error_message = (
            "Invalid topic pattern; single-level wildcard is not "
            "allowed in topic pattern %s. Use path-parameters instead "
            "(e.g. '{param}')"
        )
        _logger.error(error_message, topic_pattern)
        raise RouteValidationError(error_message, topic_pattern)

    segments = topic_pattern.split(TOPIC_SEPARATOR)
    for index, segment in enumerate(segments):
        if MULTI_LEVEL_WILDCARD in segment:
            if segment != MULTI_LEVEL_WILDCARD:
                error_message = (
                    "Invalid topic pattern; multi-level wildcard must "
                    "occupy entire segment in topic pattern %s"
                )
                _logger.error(error_message, topic_pattern)
                raise RouteValidationError(error_message, topic_pattern)

            if index != len(segments) - 1:
                error_message = (
                    "Invalid topic pattern; multi-level wildcard must "
                    "be the last segment in topic pattern %s"
                )
                _logger.error(error_message, topic_pattern)
                raise RouteValidationError(error_message, topic_pattern)

        params_in_segment = PATH_PARAMETER_PATTERN.findall(segment)
        if params_in_segment:
            expected = f"{{{params_in_segment[0]}}}"
            if len(params_in_segment) != 1 or segment != expected:
                error_message = (
                    "Invalid topic pattern; path-parameters must occupy "
                    "the entire segment (e.g. '{param}'): %s"
                )
                _logger.error(error_message, topic_pattern)
                raise RouteValidationError(error_message, topic_pattern)

            if params_in_segment[0] == WILDCARD_PARAMETER_NAME:
                error_message = (
                    "Invalid topic pattern; path-parameter name %s is "
                    "reserved: %s"
                )
                _logger.error(
                    error_message,
                    WILDCARD_PARAMETER_NAME,
                    topic_pattern,
                )
                raise RouteValidationError(
                    error_message,
                    WILDCARD_PARAMETER_NAME,
                    topic_pattern,
                )


def _validate_route_handler(handler: AnyCallable, topic_pattern: str) -> None:
    if not inspect.iscoroutinefunction(handler):
        error_message = "Invalid route handler; %s must be an async function"
        _logger.error(error_message, handler.__qualname__)
        raise RouteValidationError(error_message, handler.__qualname__)

    signature = inspect.signature(handler)
    handler_parameter_names = set(signature.parameters.keys())
    path_parameter_names = set(PATH_PARAMETER_PATTERN.findall(topic_pattern))

    if MULTI_LEVEL_WILDCARD in topic_pattern:
        path_parameter_names.add(WILDCARD_PARAMETER_NAME)

    # All path parameters in the topic pattern must have a corresponding
    # handler parameter
    missing = path_parameter_names - handler_parameter_names
    if missing:
        error_message = (
            "Invalid route handler; missing parameters for path-"
            "parameters in topic pattern %s: %r"
        )
        _logger.error(error_message, topic_pattern, missing)
        raise RouteValidationError(error_message, topic_pattern, missing)

    non_path_parameters = {
        p
        for p in signature.parameters.values()
        if p.name not in path_parameter_names
        and p.kind
        in {
            p.POSITIONAL_OR_KEYWORD,
            p.KEYWORD_ONLY,
        }
    }
    if len(non_path_parameters) > 1:
        error_message = (
            "Invalid route handler; more than one packet parameter in "
            "topic pattern %s: %r"
        )
        raise RouteValidationError(
            error_message,
            topic_pattern,
            {p.name for p in non_path_parameters},
        )


def _compile_topic_pattern(topic_pattern: str) -> re.Pattern[str]:
    """Compile ``topic_pattern`` into regex.

    Parameters
    ----------
    topic_pattern
        Topic pattern that may contain ``{param}`` placeholders.

    Returns
    -------
    re.Pattern[str]
        Compiled regex.
    """
    regex_parts: list[str] = []
    segments = topic_pattern.split(TOPIC_SEPARATOR)

    for segment in segments:
        if not segment:
            regex_parts.append("")
            continue

        match = PATH_PARAMETER_PATTERN.fullmatch(segment)
        if match is not None:
            parameter_name = match.group(1)
            regex_parts.append(f"(?P<{parameter_name}>[^{TOPIC_SEPARATOR}]+)")
            continue

        if segment == MULTI_LEVEL_WILDCARD:
            regex_parts.append("(?P<wildcard>.+)")
            break

        regex_parts.append(re.escape(segment))

    regex_pattern = "^" + TOPIC_SEPARATOR.join(regex_parts) + "$"
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
    return PATH_PARAMETER_PATTERN.sub(SINGLE_LEVEL_WILDCARD, topic_pattern)
