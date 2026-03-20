"""Serialization utilities for FastCC."""

import dataclasses
import enum
import json
import struct
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

from fastcc.codec import Codec, CodecRegistry
from fastcc.constants import BOOL_FALSE_BYTE, BOOL_TRUE_BYTE, FLOAT_BYTE_LENGTH
from fastcc.exceptions import SerializationError


class _BuiltInCodecTag(enum.IntEnum):
    """Byte prefix identifying the serialized payload type."""

    NONE = 0x00
    BYTES = 0x01
    STR = 0x02
    BOOL = 0x03
    INT = 0x04
    FLOAT = 0x05
    JSON = 0x06


@dataclasses.dataclass(frozen=True, slots=True)
class _BuiltInCodec:
    tag: _BuiltInCodecTag

    _can_encode: Callable[[typing.Any], bool]
    _encode: Callable[[typing.Any], bytes]
    _decode: Callable[[bytes], typing.Any]

    def can_encode(self, value: typing.Any) -> bool:
        return self._can_encode(value)

    def encode(self, value: typing.Any) -> bytes:
        return self._encode(value)

    def decode(self, data: bytes) -> typing.Any:
        return self._decode(data)


def _can_encode_none(value: typing.Any) -> bool:
    return value is None


def _encode_none(_: typing.Any) -> bytes:
    return b""


def _decode_none(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != 0:
        error_message = f"Invalid ``None`` payload length: {payload_length}"
        raise SerializationError(error_message)
    return None


def _can_encode_bytes(value: typing.Any) -> bool:
    return isinstance(value, bytes)


def _encode_bytes(value: typing.Any) -> bytes:
    return typing.cast(bytes, value)


def _decode_bytes(payload: bytes) -> typing.Any:
    return payload


def _can_encode_str(value: typing.Any) -> bool:
    return isinstance(value, str)


def _encode_str(value: typing.Any) -> bytes:
    str_value = typing.cast(str, value)
    return str_value.encode()


def _decode_str(payload: bytes) -> typing.Any:
    try:
        return payload.decode()
    except UnicodeDecodeError as exc:
        error_message = "Failed to decode payload as UTF-8 string"
        raise SerializationError(error_message) from exc


def _can_encode_bool(value: typing.Any) -> bool:
    return isinstance(value, bool)


def _encode_bool(value: typing.Any) -> bytes:
    bool_value = typing.cast(bool, value)
    return BOOL_TRUE_BYTE if bool_value else BOOL_FALSE_BYTE


def _decode_bool(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != 1:
        error_message = f"Invalid boolean payload length: {payload_length}"
        raise SerializationError(error_message)

    if payload not in {BOOL_FALSE_BYTE, BOOL_TRUE_BYTE}:
        error_message = f"Invalid boolean payload value: {payload!r}"
        raise SerializationError(error_message)

    return payload == BOOL_TRUE_BYTE


def _can_encode_int(value: typing.Any) -> bool:
    return isinstance(value, int)


def _encode_int(value: typing.Any) -> bytes:
    int_value = typing.cast(int, value)
    byte_length = (int_value.bit_length() + 8) // 8
    return int_value.to_bytes(byte_length, byteorder="big", signed=True)


def _decode_int(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length == 0:
        error_message = f"Invalid integer payload length: {payload_length}"
        raise SerializationError(error_message)

    return int.from_bytes(payload, byteorder="big", signed=True)


def _can_encode_float(value: typing.Any) -> bool:
    return isinstance(value, float)


def _encode_float(value: typing.Any) -> bytes:
    float_value = typing.cast(float, value)
    return struct.pack("!d", float_value)


def _decode_float(payload: bytes) -> typing.Any:
    payload_length = len(payload)
    if payload_length != FLOAT_BYTE_LENGTH:
        error_message = f"Invalid float payload length: {payload_length}"
        raise SerializationError(error_message)

    return struct.unpack("!d", payload)[0]


def _can_encode_json(value: typing.Any) -> bool:
    try:
        json.dumps(value)
    except TypeError, OverflowError:
        return False
    return True


def _encode_json(value: typing.Any) -> bytes:
    return json.dumps(value).encode()


def _decode_json(payload: bytes) -> typing.Any:
    return json.loads(payload.decode())


def _build_default_registry() -> CodecRegistry:
    registry = CodecRegistry()

    # Keep bool before int, since bool is a subclass of int and would
    # otherwise be encoded as int
    builtins: tuple[Codec, ...] = (
        _BuiltInCodec(
            tag=_BuiltInCodecTag.NONE,
            _can_encode=_can_encode_none,
            _encode=_encode_none,
            _decode=_decode_none,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.BYTES,
            _can_encode=_can_encode_bytes,
            _encode=_encode_bytes,
            _decode=_decode_bytes,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.STR,
            _can_encode=_can_encode_str,
            _encode=_encode_str,
            _decode=_decode_str,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.BOOL,
            _can_encode=_can_encode_bool,
            _encode=_encode_bool,
            _decode=_decode_bool,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.INT,
            _can_encode=_can_encode_int,
            _encode=_encode_int,
            _decode=_decode_int,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.FLOAT,
            _can_encode=_can_encode_float,
            _encode=_encode_float,
            _decode=_decode_float,
        ),
        _BuiltInCodec(
            tag=_BuiltInCodecTag.JSON,
            _can_encode=_can_encode_json,
            _encode=_encode_json,
            _decode=_decode_json,
        ),
    )

    for codec in builtins:
        registry.register(codec)

    return registry


default_registry = _build_default_registry()
"""The default codec registry with FastCC's built-in codecs."""


def serialize(
    value: typing.Any,
    registry: CodecRegistry | None = None,
) -> bytes:
    """Serialize a value using the given codec registry.

    Parameters
    ----------
    value
        The value to serialize.
    registry
        The codec registry to use for serialization. If ``None``, the
        default registry with FastCC's built-in codecs is used.

    Returns
    -------
    bytes
        The serialized value, prefixed with the codec's type tag.
    """
    if registry is None:
        registry = default_registry

    return registry.encode(value)


def deserialize(
    data: bytes,
    registry: CodecRegistry | None = None,
) -> typing.Any:
    """Deserialize data using the given codec registry.

    Parameters
    ----------
    data
        The data to deserialize, prefixed with the codec's type tag.
    registry
        The codec registry to use for deserialization. If ``None``, the
        default registry with FastCC's built-in codecs is used.

    Returns
    -------
    Any
        The deserialized value.
    """
    if registry is None:
        registry = default_registry

    return registry.decode(data)
