import dataclasses
import inspect
import re
import typing
from collections.abc import Awaitable, Callable

if typing.TYPE_CHECKING:
    from fastcc.client import SubscribeContext

from fastcc.constants import (
    MULTI_LEVEL_WILDCARD,
    PATH_PARAMETER_PATTERN,
    SINGLE_LEVEL_WILDCARD,
    TOPIC_SEPARATOR,
    WILDCARD_PARAMETER_NAME,
)
from fastcc.exceptions import RouteValidationError

type Routable = Callable[..., Awaitable[typing.Any]]


@dataclasses.dataclass(frozen=True, slots=True)
class Route:
    """Endpoint for a subscription."""

    pattern: str
    handler: Routable
    context: SubscribeContext | None = None

    regex: re.Pattern = dataclasses.field(init=False)
    injectors: frozenset[str] = dataclasses.field(init=False)
    payload_type: type[typing.Any] = dataclasses.field(init=False)
    return_type: type[typing.Any] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        _validate_pattern(self.pattern)
        _validate_handler(self.handler, self.pattern)

        object.__setattr__(self, "regex", _compile_pattern(self.pattern))
        object.__setattr__(
            self,
            "injectors",
            _extract_injectors(self.handler, self.pattern),
        )
        object.__setattr__(
            self,
            "payload_type",
            _extract_payload_type(self.handler),
        )
        object.__setattr__(
            self,
            "return_type",
            _extract_return_type(self.handler),
        )

    async def __call__(
        self,
        value: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """Invoke the route's handler with the given payload.

        Parameters
        ----------
        payload
            The payload to pass to the handler function.
        kwargs
            Path parameters extracted from the topic, where keys are
            parameter names and values are the corresponding values
            from the topic plus possible injector values.

        Returns
        -------
        bytes | None
            The result returned by the handler function, or ``None`` if
            the handler does not return a value.
        """
        return await self.handler(value, **kwargs)

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


def _validate_pattern(pattern: str) -> None:
    if not pattern:
        error_message = "Route pattern cannot be empty"
        raise RouteValidationError(error_message)

    if SINGLE_LEVEL_WILDCARD in pattern:
        error_message = (
            f"Route pattern cannot contain single-level wildcard "
            f"{SINGLE_LEVEL_WILDCARD!r}. Use path-parameters (e.g. "
            f"'{{param}}') instead"
        )
        raise RouteValidationError(error_message)

    segments = pattern.split(TOPIC_SEPARATOR)
    for i, segment in enumerate(segments):
        if MULTI_LEVEL_WILDCARD in segment:
            if segment != MULTI_LEVEL_WILDCARD:
                error_message = (
                    f"Multi-level wildcard {MULTI_LEVEL_WILDCARD!r} "
                    f"must occupy an entire segment in the route "
                    f"pattern: {pattern}"
                )
                raise RouteValidationError(error_message)

            if i != len(segments) - 1:
                error_message = (
                    f"Multi-level wildcard {MULTI_LEVEL_WILDCARD!r} "
                    f"must be the last segment in the route pattern: "
                    f"{pattern}"
                )
                raise RouteValidationError(error_message)

        if "{" in segment or "}" in segment:
            if (match := re.fullmatch(PATH_PARAMETER_PATTERN, segment)) is None:
                error_message = (
                    f"Path-parameters must occupy an entire segment "
                    f"in the route pattern: {pattern}"
                )
                raise RouteValidationError(error_message)

            path_parameter_name = match.group(1)
            if path_parameter_name[0].isdigit():
                error_message = (
                    f"Path-parameter names must start with a letter or "
                    f"underscore in route pattern: {pattern}"
                )
                raise RouteValidationError(error_message)


def _validate_handler(handler: Routable, pattern: str) -> None:
    if not inspect.iscoroutinefunction(handler):
        error_message = f"Route handler {handler!r} must be asynchronous"
        raise RouteValidationError(error_message)

    signature = inspect.signature(handler)
    positional_params = [
        p
        for p in signature.parameters.values()
        if p.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    if len(positional_params) != 1:
        error_message = (
            f"Route handler {handler!r} must have exactly one "
            f"positional parameter (the payload parameter). Did you "
            f"forget to add ``*`` to the parameter list?"
        )
        raise ValueError(error_message)

    keyword_only_params = {
        p.name
        for p in signature.parameters.values()
        if p.kind == inspect.Parameter.KEYWORD_ONLY
    }
    path_parameters: set[str] = set(re.findall(PATH_PARAMETER_PATTERN, pattern))
    if MULTI_LEVEL_WILDCARD in pattern:
        path_parameters.add(WILDCARD_PARAMETER_NAME)

    missing = path_parameters - keyword_only_params
    if missing:
        error_message = (
            f"Route handler {handler!r} is missing path-parameters: {missing}"
        )
        raise RouteValidationError(error_message)


def _compile_pattern(pattern: str) -> re.Pattern:
    # Replace path-parameter with regex equivalent
    pattern = re.sub(PATH_PARAMETER_PATTERN, r"(?P<\1>[^/]+)", pattern)

    # Replace multi-level wildcard with regex equivalent
    pattern = pattern.replace(
        MULTI_LEVEL_WILDCARD,
        rf"(?P<{WILDCARD_PARAMETER_NAME}>.*)",
    )

    return re.compile(pattern)


def _extract_injectors(handler: Routable, pattern: str) -> frozenset[str]:
    signature = inspect.signature(handler)
    keyword_only_params = {
        p.name
        for p in signature.parameters.values()
        if p.kind == inspect.Parameter.KEYWORD_ONLY
    }
    path_parameters: set[str] = set(re.findall(PATH_PARAMETER_PATTERN, pattern))
    if MULTI_LEVEL_WILDCARD in pattern:
        path_parameters.add(WILDCARD_PARAMETER_NAME)

    return frozenset(keyword_only_params - path_parameters)


def _extract_payload_type(handler: Routable) -> type[typing.Any]:
    signature = inspect.signature(handler)
    positional_params = [
        p
        for p in signature.parameters.values()
        if p.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    payload_param = positional_params[0]
    return payload_param.annotation  # type: ignore[no-any-return]


def _extract_return_type(handler: Routable) -> type[typing.Any]:
    signature = inspect.signature(handler)
    return signature.return_annotation  # type: ignore[no-any-return]
