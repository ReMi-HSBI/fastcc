"""Functions to analyze code and data structures."""

from __future__ import annotations

import inspect
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

    from fastcc.utilities.type_aliases import Routable

from fastcc.utilities import constants
from fastcc.utilities.interpretation import bytes_to_packet


def extract_route_kwargs(
    routable: Routable,
    message: aiomqtt.Message,
    injectors: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Extract the keyword arguments of a routable from a message.

    Parameters
    ----------
    routable
        Routable to extract the keyword arguments for.
    message
        Message to extract the keyword arguments from.
    injectors
        Injectors to use for the keyword arguments.

    Returns
    -------
    dict[str, Any]
        Keyword arguments.
    """
    assert isinstance(message.payload, bytes)  # noqa: S101

    # Make sure to not change out-of-scope injectors.
    injectors = injectors.copy()

    signature = inspect.signature(routable, eval_str=True)
    parameters = signature.parameters

    kwargs = {
        key: value for key, value in injectors.items() if key in parameters
    }

    if constants.MESSAGE_INJECTOR_FIELD in parameters:
        kwargs[constants.MESSAGE_INJECTOR_FIELD] = message

    if packet_parameter := find_packet_parameter(routable):
        packet = bytes_to_packet(message.payload, packet_parameter.annotation)
        kwargs[packet_parameter.name] = packet

    return kwargs


def find_packet_parameter(routable: Routable) -> inspect.Parameter | None:
    """Find the packet parameter of a routable.

    The packet parameter is the first (and only) positional parameter of
    a routable.

    Parameters
    ----------
    routable
        Routable to get the packet parameter from.

    Returns
    -------
    inspect.Parameter
        Packet parameter.
    None
        If the routable has no packet parameter.
    """
    signature = inspect.signature(routable, eval_str=True)
    parameters = list(signature.parameters.values())

    if len(parameters) == 0:
        return None

    potential = parameters[0]
    if potential.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD:
        return None

    return potential
