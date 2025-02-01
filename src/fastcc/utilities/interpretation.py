"""Route validation functions."""

from __future__ import annotations

import inspect
import struct
import typing

if typing.TYPE_CHECKING:
    from fastcc.utilities.type_aliases import Routable
    from fastcc.utilities.type_definitions import Packet

from google.protobuf.message import Message


def get_packet_parameter(routable: Routable) -> inspect.Parameter | None:
    """Get the packet parameter of a routable.

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

    try:
        p0 = parameters.pop(0)
    except IndexError:
        p0 = None

    if p0 is None:
        return None

    if p0.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD:
        return None

    return p0


def bytes_to_packet[T: Packet](payload: bytes, packet_type: type[T]) -> T:
    """Convert bytes to a packet.

    Parameters
    ----------
    payload
        Payload to convert.
    packet_type
        Packet type to convert to.

    Returns
    -------
    Packet
        Converted packet.
    """
    if issubclass(packet_type, bytes):
        return payload  # type: ignore [return-value]

    if issubclass(packet_type, str):
        return payload.decode()  # type: ignore [return-value]

    if issubclass(packet_type, int):
        return int.from_bytes(payload)  # type: ignore [return-value]

    if issubclass(packet_type, float):
        return struct.unpack("f", payload)[0]  # type: ignore [no-any-return]

    if issubclass(packet_type, Message):
        message = packet_type()
        message.ParseFromString(payload)
        return message  # type: ignore [return-value]

    details = f"packet type {packet_type} is not supported"
    raise NotImplementedError(details)
