"""Module defining the ``serialize`` and ``deserialize`` functions."""

import enum
import logging
import struct
import typing

import google.protobuf.message as pb2_message

from fastcc.annotations import Packet
from fastcc.constants import (
    BOOL_FALSE_BYTE,
    BOOL_TRUE_BYTE,
    FLOAT_BYTE_LENGTH,
    MAX_PAYLOAD_SIZE,
)
from fastcc.exceptions import SerializationError

_logger = logging.getLogger(__name__)

__all__ = ["deserialize", "serialize"]


class _TypeTag(enum.IntEnum):
    """Byte prefix identifying the serialized payload type."""

    NONE = 0x00
    BYTES = 0x01
    STR = 0x02
    INT = 0x03
    FLOAT = 0x04
    BOOL = 0x05
    PROTOBUF = 0x06


def serialize(packet: Packet) -> bytes:
    """Serialize ``packet`` into bytes for transmission.

    This function converts a ``Packet`` object into a byte string that
    can be transmitted over MQTT. A single-byte type prefix is prepended
    so that the deserializer can unambiguously reconstruct the original
    value — including distinguishing ``None`` from an empty ``bytes``
    object.

    Parameters
    ----------
    packet
        Packet to serialize.

    Returns
    -------
    bytes
        Serialized byte string representation of the packet.

    Raises
    ------
    SerializationError
        If the packet cannot be serialized due to an unsupported payload
        type or other serialization issues.
    """
    tag: int
    payload: bytes

    if packet is None:
        return bytes([_TypeTag.NONE])

    # bool must be checked before int (bool is a subclass of int).
    if isinstance(packet, bool):
        tag = _TypeTag.BOOL
        payload = BOOL_TRUE_BYTE if packet else BOOL_FALSE_BYTE
    elif isinstance(packet, bytes):
        tag = _TypeTag.BYTES
        payload = packet
    elif isinstance(packet, str):
        tag = _TypeTag.STR
        payload = packet.encode("utf-8")
    elif isinstance(packet, int):
        tag = _TypeTag.INT
        # Encode as signed, variable-length big-endian integer.
        byte_len = (packet.bit_length() + 8) // 8  # +8 for sign bit
        payload = packet.to_bytes(byte_len, byteorder="big", signed=True)
    elif isinstance(packet, float):
        tag = _TypeTag.FLOAT
        payload = struct.pack("!d", packet)  # IEEE 754 double
    elif isinstance(packet, pb2_message.Message):
        tag = _TypeTag.PROTOBUF
        payload = packet.SerializeToString()
    else:
        error_message = "Unsupported packet type: %s"  # type: ignore[unreachable]
        raise SerializationError(error_message, type(packet).__name__)

    return bytes([tag]) + payload


def deserialize(data: bytes) -> Packet:  # noqa: C901, PLR0911, PLR0912
    """Deserialize ``data`` back into the original packet value.

    This function is the inverse of ``serialize``. It reads the
    single-byte type prefix to determine which Python type to
    reconstruct, then decodes the remaining bytes accordingly.

    Parameters
    ----------
    data
        Raw bytes previously produced by ``serialize``.

    Returns
    -------
    Packet
        Reconstructed Python object.

    Raises
    ------
    SerializationError
        If ``data`` is empty or contains an unrecognised type tag.

    Notes
    -----
    Protobuf payloads are returned as raw ``bytes`` because the concrete
    ``Message`` subclass is not known at this level. The caller is
    responsible for parsing them with the appropriate generated class
    via ``ParseFromString``.
    """
    if not data:
        error_message = "Cannot deserialize empty data"
        _logger.error(error_message)
        raise SerializationError(error_message)

    tag = data[0]
    payload = data[1:]
    payload_length = len(payload)

    if payload_length > MAX_PAYLOAD_SIZE:
        error_message = "Payload size exceeds maximum limit: %d bytes"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)

    if tag == _TypeTag.NONE:
        if payload_length != 0:
            error_message = "Invalid None payload length: %s"
            _logger.error(error_message, payload_length)
            raise SerializationError(error_message, payload_length)
        return None

    if tag == _TypeTag.BOOL:
        if payload_length != 1:
            error_message = "Invalid boolean payload length: %s"
            _logger.error(error_message, payload_length)
            raise SerializationError(error_message, payload_length)
        if payload not in {BOOL_FALSE_BYTE, BOOL_TRUE_BYTE}:
            error_message = "Invalid boolean payload value: %s"
            _logger.error(error_message, payload)
            raise SerializationError(error_message, payload)

        return payload == BOOL_TRUE_BYTE

    if tag == _TypeTag.BYTES:
        return payload

    if tag == _TypeTag.STR:
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            error_message = "Failed to decode UTF-8 string: %s"
            raise SerializationError(error_message, exc) from exc

    if tag == _TypeTag.INT:
        if payload_length == 0:
            error_message = "Invalid integer payload length: %s"
            _logger.error(error_message, payload_length)
            raise SerializationError(error_message, payload_length)

        return int.from_bytes(payload, byteorder="big", signed=True)

    if tag == _TypeTag.FLOAT:
        if payload_length != FLOAT_BYTE_LENGTH:
            error_message = "Invalid float payload length: %s"
            _logger.error(error_message, payload_length)
            raise SerializationError(error_message, payload_length)

        return typing.cast("float", struct.unpack("!d", payload)[0])

    if tag == _TypeTag.PROTOBUF:
        # Return raw bytes; the caller must parse them with
        # the appropriate protobuf Message subclass.
        return payload

    error_message = "Unrecognised type tag: 0x%02x"
    _logger.error(error_message, tag)
    raise SerializationError(error_message, tag)
