"""Route validation functions."""

from __future__ import annotations

import struct
import types
import typing

if typing.TYPE_CHECKING:
    from fastcc.utilities.type_definitions import Packet

from google.protobuf.message import Message


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

    if packet_type is types.NoneType:
        return None  # type: ignore [return-value]

    details = f"Packet type {packet_type} is not supported"
    raise NotImplementedError(details)
