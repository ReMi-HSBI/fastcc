"""Route validation functions."""

from __future__ import annotations

import inspect
import logging
import types
import typing
from collections.abc import AsyncIterator

if typing.TYPE_CHECKING:
    from fastcc.utilities.type_aliases import Routable

from fastcc.utilities.type_definitions import Packet

_logger = logging.getLogger(__name__)


def validate_route(routable: Routable) -> None:
    """Check if a routable is valid.

    Parameters
    ----------
    routable
        Routable to validate.
    """
    signature = inspect.signature(routable, eval_str=True)
    parameters = list(signature.parameters.values())

    try:
        p0 = parameters.pop(0)
    except IndexError:
        p0 = None

    if p0 is not None:
        validate_route_first_parameter(p0)

    validate_keyword_only_parameters(parameters)
    validate_return_type(signature.return_annotation, routable)


def validate_route_first_parameter(p0: inspect.Parameter) -> None:
    """Check if the first parameter of a route is valid.

    Parameters
    ----------
    p0
        First parameter of a route.

    Raises
    ------
    ValueError
        If the first parameter is invalid.
    """
    allowed_p0_kinds = {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
    if p0.kind not in allowed_p0_kinds:
        details = (
            f"first parameter must be positional (packet) "
            f"or keyword-only (injector), not {p0.kind!r}"
        )
        _logger.error(details)
        raise ValueError(details)

    if p0.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
        # p0 is packet parameter => verify type
        if p0.annotation is inspect.Parameter.empty:
            details = "packet parameter must have a type annotation"
            _logger.error(details)
            raise ValueError(details)

        if type(p0.annotation) is types.UnionType:
            details = (
                f"packet parameter with type {types.UnionType} is "
                f"not supported yet"
            )
            _logger.error(details)
            raise NotImplementedError(details)

        try:
            success = issubclass(p0.annotation, Packet)
        except TypeError:
            success = False

        if not success:
            details = (
                f"packet parameter must be of type {Packet} not {p0.annotation}"
            )
            _logger.error(details)
            raise ValueError(details)


def validate_keyword_only_parameters(
    parameters: list[inspect.Parameter],
) -> None:
    """Check if all parameters are keyword-only.

    Parameters
    ----------
    parameters
        Parameters to validate.

    Raises
    ------
    ValueError
        If a parameter is not keyword-only.
    """
    for p in parameters:
        if p.kind != inspect.Parameter.KEYWORD_ONLY:
            details = f"parameter '{p}' must be keyword-only, not {p.kind!r}"
            _logger.error(details)
            raise ValueError(details)


def validate_return_type(  # noqa: C901
    return_annotation: typing.Any,
    routable: Routable,
) -> None:
    """Check if the return type is valid.

    Parameters
    ----------
    return_annotation
        Return type to validate.
    routable
        Routable to validate.

    Raises
    ------
    ValueError
        If the return type is invalid.
    """
    if return_annotation is inspect.Parameter.empty:
        details = "return value must have a type annotation"
        _logger.error(details)
        raise ValueError(details)

    if return_annotation is None:
        return

    if type(return_annotation) is types.UnionType:
        details = (
            f"return value with type {types.UnionType} is not supported yet"
        )
        _logger.error(details)
        raise NotImplementedError(details)

    if inspect.isasyncgenfunction(routable):
        if return_annotation.__origin__ is not AsyncIterator:
            details = (
                "return value must be of type "
                "collections.abc.AsyncIterator[Packet]"
            )
            _logger.error(details)
            raise ValueError(details)

        if len(return_annotation.__args__) != 1:
            details = (
                "return value must be of type "
                "collections.abc.AsyncIterator[Packet]"
            )
            _logger.error(details)
            raise ValueError(details)

        return_annotation = return_annotation.__args__[0]
        if return_annotation is Packet:
            return

        if type(return_annotation) is types.UnionType:
            details = (
                f"return value with type {types.UnionType} is not supported yet"
            )

        if issubclass(return_annotation, Packet):
            return

        success = False

    else:
        try:
            success = issubclass(return_annotation, Packet)
        except TypeError:
            success = False

    if not success:
        details = (
            f"return value must be of type {Packet} not {return_annotation}"
        )
        _logger.error(details)
        raise ValueError(details)
