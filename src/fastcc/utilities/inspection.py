"""Module defining FastCC specific utilities for inspection.

This module defines utilities that are built on top of the ``inspect``
module to provide a higher-level interface for inspecting FastCC
specific constructs.
"""

import inspect
import logging
from collections.abc import Iterable

from fastcc.exceptions import FastCCError
from fastcc.utilities.annotations import RouteHandler

_logger = logging.getLogger(__name__)


def get_packet_parameter(
    func: RouteHandler,
    exclude: Iterable[str] | None = None,
) -> inspect.Parameter | None:
    """Get the packet parameter from a function's signature.

    This function inspects the signature of the given function and
    returns the parameter that is annotated as a packet, if it exists.
    If no such parameter is found, it returns ``None``.`

    A packet parameter is the first positional or positional-keyword
    parameter that is not a path-parameter.

    Parameters
    ----------
    func
        The function whose signature is to be inspected.
    exclude
        An iterable of parameter names to exclude from consideration.
        This is typically used to exclude path-parameters.

    Returns
    -------
    inspect.Parameter | None
        The parameter annotated as a packet, or ``None`` if no such
        parameter exists.

    Raises
    ------
    FastCCError
        If the function has more than one packet parameter.
    """
    if exclude is None:
        exclude = set()

    signature = inspect.signature(func)
    potential_packet_parameters: set[inspect.Parameter] = {
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
        and parameter.name not in exclude
    }
    if not potential_packet_parameters:
        return None

    if len(potential_packet_parameters) != 1:
        error_message = (
            "Function %r has more than one potential packet parameter: %r"
        )
        error_data = (func.__qualname__, potential_packet_parameters)
        _logger.error(error_message, *error_data)
        raise FastCCError(error_message, *error_data)

    return potential_packet_parameters.pop()


def get_injector_parameters(
    func: RouteHandler,
    exclude: Iterable[str] | None = None,
) -> set[inspect.Parameter]:
    """Get the injector parameters from a function's signature.

    This function inspects the signature of the given function and
    returns a set of parameters that are annotated as injectors. These
    are the keyword-only parameters that are not path-parameters.

    Parameters
    ----------
    func
        The function whose signature is to be inspected.
    exclude
        An iterable of parameter names to exclude from consideration.
        This is typically used to exclude path-parameters.

    Returns
    -------
    set[inspect.Parameter]
        A set of parameters annotated as injectors.
    """
    if exclude is None:
        exclude = set()

    signature = inspect.signature(func)
    return {
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind == inspect.Parameter.KEYWORD_ONLY
        and parameter.name not in exclude
    }
