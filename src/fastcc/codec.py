"""Codec protocol and registry used by FastCC serialization."""

import typing

from fastcc.constants import MAX_CODEC_TAG
from fastcc.exceptions import SerializationError

__all__ = ["Codec", "CodecRegistry"]


class Codec(typing.Protocol):
    """Codec interface for serializing and deserializing one value kind."""

    tag: int

    def can_encode(self, value: typing.Any) -> bool:
        """Return ``True`` if ``value`` can be encoded by this codec."""

    def encode(self, value: typing.Any) -> bytes:
        """Encode ``value`` into payload bytes (without type tag)."""

    def decode(self, payload: bytes) -> typing.Any:
        """Decode payload bytes (without type tag) into a Python value."""


class CodecRegistry:
    """Registry that manages codecs and performs tagged (de-)serialization."""

    def __init__(self, codecs: typing.Iterable[Codec] | None = None) -> None:
        self._codecs_by_tag: dict[int, Codec] = {}
        self._codecs_by_order: list[Codec] = []

        if codecs is not None:
            for codec in codecs:
                self.register(codec)

    def clone(self) -> CodecRegistry:
        """Return a shallow copy with the same codec registrations.

        Returns
        -------
        CodecRegistry
            New registry instance with the same codec ordering and tags.
        """
        return CodecRegistry(self._codecs_by_order)

    def register(self, codec: Codec, *, override: bool = False) -> None:
        """Register ``codec``.

        Parameters
        ----------
        codec
            Codec instance to register.
        override
            Whether an existing codec with the same tag should be replaced.

        Raises
        ------
        SerializationError
            If the tag is invalid or already registered without ``override``.
        """
        tag = codec.tag
        if isinstance(tag, bool) or not isinstance(tag, int):
            error_message = "Codec tag must be an integer in range 0..255: %r"
            raise SerializationError(error_message, tag)

        if not 0 <= tag <= MAX_CODEC_TAG:
            error_message = "Codec tag out of range 0..255: %d"
            raise SerializationError(error_message, tag)

        existing_codec = self._codecs_by_tag.get(tag)
        if existing_codec is not None and not override:
            error_message = "Codec tag already registered: 0x%02x"
            raise SerializationError(error_message, tag)

        if existing_codec is not None and override:
            for index, current in enumerate(self._codecs_by_order):
                if current.tag == tag:
                    self._codecs_by_order[index] = codec
                    break
        else:
            self._codecs_by_order.append(codec)

        self._codecs_by_tag[tag] = codec

    def encode(self, value: typing.Any) -> bytes:
        """Encode ``value`` using the first codec that can handle it.

        Parameters
        ----------
        value
            Value to encode.

        Returns
        -------
        bytes
            Serialized bytes including the leading type tag.

        Raises
        ------
        SerializationError
            If no registered codec can encode ``value``.
        """
        for codec in self._codecs_by_order:
            if codec.can_encode(value):
                payload = codec.encode(value)
                return bytes([codec.tag]) + payload

        error_message = "Unsupported packet type: %s"
        raise SerializationError(error_message, type(value).__name__)

    def decode(self, data: bytes) -> typing.Any:
        """Decode ``data`` using the codec associated with the leading tag.

        Parameters
        ----------
        data
            Serialized bytes including the leading type tag.

        Returns
        -------
        typing.Any
            Decoded Python value.

        Raises
        ------
        SerializationError
            If ``data`` is empty or the tag is unknown.
        """
        if not data:
            error_message = "Cannot deserialize empty data"
            raise SerializationError(error_message)

        tag = data[0]
        payload = data[1:]
        codec = self._codecs_by_tag.get(tag)
        if codec is None:
            error_message = "Unrecognised type tag: 0x%02x"
            raise SerializationError(error_message, tag)

        return codec.decode(payload)
