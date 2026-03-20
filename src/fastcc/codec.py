"""Codec protocol and registry used by FastCC for serialization."""

import typing

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

from fastcc.constants import MAX_CODEC_TAG
from fastcc.exceptions import (
    CodecConflictError,
    InvalidCodecTagError,
    SerializationError,
)


class Codec(typing.Protocol):
    """Codec interface for serializing and deserializing one value kind."""

    @property
    def tag(self) -> int:
        """Type tag identifying this codec."""

    def can_encode(self, value: typing.Any) -> bool:
        """Check if the codec can encode the given value.

        Parameters
        ----------
        value
            The value to check.

        Returns
        -------
        bool
            `True` if the codec can encode the value, `False` otherwise.
        """

    def encode(self, value: typing.Any) -> bytes:
        """Encode the given value.

        Parameters
        ----------
        value
            The value to encode.

        Returns
        -------
        bytes
            The encoded value.

        Notes
        -----
        It is expected that the caller has already verified that the
        codec can encode the value using `can_encode()`.
        """

    def decode(self, data: bytes) -> typing.Any:
        """Decode the given data.

        Parameters
        ----------
        data
            The data to decode (without the type tag).

        Returns
        -------
        Any
            The decoded value.
        """


class CodecRegistry:
    """Registry that manages codecs and perform tagged (de-)serialization."""

    def __init__(self, codecs: Iterable[Codec] | None = None) -> None:
        self._codecs: dict[int, Codec] = {}

        if codecs:
            for codec in codecs:
                self.register(codec)

    def clone(self) -> CodecRegistry:
        """Return a shallow copy with the same codec registrations.

        Returns
        -------
        CodecRegistry
            A new `CodecRegistry` instance with the same codec registrations.
        """
        return CodecRegistry(codecs=self._codecs.values())

    def register(self, codec: Codec, *, override: bool = False) -> None:
        """Register a codec.

        Parameters
        ----------
        codec
            The codec to register.
        override
            Whether an existing codec with the same tag should be replaced.

        Raises
        ------
        InvalidCodecTagError
            If the codec is invalid (e.g., if the tag is out of range).
        CodecConflictError
            If a codec with the same tag is already registered and
            ``override`` is ``False``.
        """
        tag = codec.tag
        if isinstance(tag, bool) or not isinstance(tag, int):
            raise InvalidCodecTagError(tag=tag)

        if not 0 <= tag <= MAX_CODEC_TAG:
            raise InvalidCodecTagError(tag=tag)

        if tag in self._codecs and not override:
            raise CodecConflictError(tag=tag)

        self._codecs[tag] = codec

    def encode(self, value: typing.Any) -> bytes:
        """Encode a value using the first compatible codec.

        Parameters
        ----------
        value
            The value to encode.

        Returns
        -------
        bytes
            The encoded value, prefixed with the codec's type tag.

        Raises
        ------
        SerializationError
            If no compatible codec is found for the given value.
        """
        for codec in self._codecs.values():
            if codec.can_encode(value):
                return bytes([codec.tag]) + codec.encode(value)

        error_message = f"No compatible codec found for value: {value}"
        raise SerializationError(error_message)

    def decode(self, data: bytes) -> typing.Any:
        """Decode data using the codec specified by the type tag.

        Parameters
        ----------
        data
            The data to decode, prefixed with the codec's type tag.

        Returns
        -------
        Any
            The decoded value.

        Raises
        ------
        InvalidCodecTagError
            If the type tag is invalid or does not correspond to a
            registered codec.
        """
        if not data:
            raise InvalidCodecTagError(tag=None)

        tag = data[0]
        codec = self._codecs.get(tag)
        if codec is None:
            raise InvalidCodecTagError(tag=tag)

        return codec.decode(data[1:])
