"""Module defining flexible ``serialize`` and ``deserialize`` functions."""

import enum
import json
import logging
import struct
import typing
from collections.abc import Callable

from fastcc.codec import Codec, CodecRegistry
from fastcc.constants import (
    BOOL_FALSE_BYTE,
    BOOL_TRUE_BYTE,
    FLOAT_BYTE_LENGTH,
    MAX_PAYLOAD_SIZE,
)
from fastcc.exceptions import SerializationError

_logger = logging.getLogger(__name__)

__all__ = ["default_registry", "deserialize", "serialize"]


class _TypeTag(enum.IntEnum):
    """Byte prefix identifying the serialized payload type."""

    NONE = 0x00
    BYTES = 0x01
    STR = 0x02
    INT = 0x03
    FLOAT = 0x04
    BOOL = 0x05
    JSON = 0x06


type _EncoderCheck = Callable[[typing.Any], bool]
type _Encoder = Callable[[typing.Any], bytes]
type _Decoder = Callable[[bytes], typing.Any]


class _SimpleCodec:
    def __init__(
        self,
        tag: int,
        can_encode: _EncoderCheck,
        encode: _Encoder,
        decode: _Decoder,
    ) -> None:
        self.tag = tag
        self._can_encode = can_encode
        self._encode = encode
        self._decode = decode

    def can_encode(self, value: typing.Any) -> bool:
        return self._can_encode(value)

    def encode(self, value: typing.Any) -> bytes:
        return self._encode(value)

    def decode(self, payload: bytes) -> typing.Any:
        return self._decode(payload)


def _encode_none(_: typing.Any) -> bytes:
    return b""


def _decode_none(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != 0:
        error_message = "Invalid None payload length: %s"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)
    return None


def _encode_bool(value: typing.Any) -> bytes:
    return BOOL_TRUE_BYTE if typing.cast(bool, value) else BOOL_FALSE_BYTE


def _decode_bool(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != 1:
        error_message = "Invalid boolean payload length: %s"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)

    if payload not in {BOOL_FALSE_BYTE, BOOL_TRUE_BYTE}:
        error_message = "Invalid boolean payload value: %s"
        _logger.error(error_message, payload)
        raise SerializationError(error_message, payload)

    return payload == BOOL_TRUE_BYTE


def _encode_bytes(value: typing.Any) -> bytes:
    return typing.cast(bytes, value)


def _decode_bytes(payload: bytes) -> typing.Any:
    return payload


def _encode_string(value: typing.Any) -> bytes:
    return typing.cast(str, value).encode("utf-8")


def _decode_string(payload: bytes) -> typing.Any:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        error_message = "Failed to decode UTF-8 string: %s"
        raise SerializationError(error_message, exc) from exc


def _encode_int(value: typing.Any) -> bytes:
    integer = typing.cast(int, value)
    byte_len = (integer.bit_length() + 8) // 8
    return integer.to_bytes(byte_len, byteorder="big", signed=True)


def _decode_int(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length == 0:
        error_message = "Invalid integer payload length: %s"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)

    return int.from_bytes(payload, byteorder="big", signed=True)


def _encode_float(value: typing.Any) -> bytes:
    return struct.pack("!d", typing.cast(float, value))


def _decode_float(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != FLOAT_BYTE_LENGTH:
        error_message = "Invalid float payload length: %s"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)

    return struct.unpack("!d", payload)[0]


def _can_encode_json(value: typing.Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, OverflowError):
        return False


def _encode_json(value: typing.Any) -> bytes:
    return json.dumps(value).encode("utf-8")


def _decode_json(payload: bytes) -> typing.Any:
    return json.loads(payload.decode("utf-8"))


def _build_default_registry() -> CodecRegistry:
    registry = CodecRegistry()

    # Keep bool before int: bool is a subclass of int.
    builtins: tuple[Codec, ...] = (
        _SimpleCodec(
            tag=int(_TypeTag.NONE),
            can_encode=lambda value: value is None,
            encode=_encode_none,
            decode=_decode_none,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.BOOL),
            can_encode=lambda value: isinstance(value, bool),
            encode=_encode_bool,
            decode=_decode_bool,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.BYTES),
            can_encode=lambda value: isinstance(value, bytes),
            encode=_encode_bytes,
            decode=_decode_bytes,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.STR),
            can_encode=lambda value: isinstance(value, str),
            encode=_encode_string,
            decode=_decode_string,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.INT),
            can_encode=lambda value: (
                isinstance(value, int) and not isinstance(value, bool)
            ),
            encode=_encode_int,
            decode=_decode_int,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.FLOAT),
            can_encode=lambda value: isinstance(value, float),
            encode=_encode_float,
            decode=_decode_float,
        ),
        _SimpleCodec(
            tag=int(_TypeTag.JSON),
            can_encode=_can_encode_json,
            encode=_encode_json,
            decode=_decode_json,
        ),
    )
    for codec in builtins:
        registry.register(codec)

    return registry


default_registry = _build_default_registry()
"""Default codec registry with FastCC built-in codecs."""


def serialize(
    packet: typing.Any,
    *,
    registry: CodecRegistry | None = None,
) -> bytes:
    """Serialize ``packet`` into bytes for transmission.

    Parameters
    ----------
    packet
        Value to serialize.
    registry
        Codec registry to use. If ``None``, ``default_registry`` is used.

    Returns
    -------
    bytes
        Serialized byte string representation of ``packet``.
    """
    selected_registry = default_registry if registry is None else registry
    return selected_registry.encode(packet)


def deserialize(
    data: bytes,
    *,
    registry: CodecRegistry | None = None,
) -> typing.Any:
    """Deserialize ``data`` back into the original packet value.

    Parameters
    ----------
    data
        Raw bytes previously produced by ``serialize``.
    registry
        Codec registry to use. If ``None``, ``default_registry`` is used.

    Returns
    -------
    typing.Any
        Reconstructed Python object.

    Raises
    ------
    SerializationError
        If ``data`` is empty or payload size exceeds the configured limit.
    """
    if not data:
        error_message = "Cannot deserialize empty data"
        _logger.error(error_message)
        raise SerializationError(error_message)

    payload_length = len(data) - 1
    if payload_length > MAX_PAYLOAD_SIZE:
        error_message = "Payload size exceeds maximum limit: %d bytes"
        _logger.error(error_message, payload_length)
        raise SerializationError(error_message, payload_length)

    selected_registry = default_registry if registry is None else registry
    return selected_registry.decode(data)
