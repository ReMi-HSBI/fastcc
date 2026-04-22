import enum
import typing

from google.protobuf.message import Message


class CodecType(enum.IntEnum):
    """Enumeration of codec types."""

    BYTES = 1
    """Codec for encoding and decoding bytes."""

    STRING = 2
    """Codec for encoding and decoding strings."""

    PROTOBUF = 3
    """Codec for encoding and decoding protobuf messages."""


class Codec(typing.Protocol):
    """Protocol for codecs that can parse values to and from bytes."""

    codec_type: int

    def can_encode(self, value: typing.Any) -> bool:
        """Check if the codec can encode the given value.

        Parameters
        ----------
        value
            The value to check for compatibility.

        Returns
        -------
        bool
            ``True`` if the codec can encode the value, ``False`` otherwise.
        """

    def can_decode(self, target_type: type[typing.Any]) -> bool:
        """Check if the codec can decode data into the target type.

        Parameters
        ----------
        target_type
            The type to check for compatibility.

        Returns
        -------
        bool
            ``True`` if the codec can decode data into the target type,
            ``False`` otherwise.
        """

    def encode(self, value: typing.Any) -> bytes:
        """Encode a value into bytes.

        Parameters
        ----------
        value
            The value to encode.

        Returns
        -------
        bytes
            The encoded value.

        Raises
        ------
        CodecError
            If the codec cannot encode the given value.

        Notes
        -----
        This method does not check for compatibility before encoding.
        It is the caller's responsibility to ensure that the codec can
        encode the value, by using ``can_encode``.
        """

    def decode[T](self, data: bytes, target_type: type[T]) -> T:
        """Decode bytes into a value of the target type.

        Parameters
        ----------
        data
            The data to decode.
        target_type
            The type to decode the data into.

        Returns
        -------
        T
            The decoded value.

        Raises
        ------
        CodecError
            If the codec cannot decode the data into the target type.

        Notes
        -----
        This method does not check for compatibility before decoding.
        It is the caller's responsibility to ensure that the codec can
        decode the data into the target type, by using ``can_decode``.
        """


class BytesCodec:
    """Codec for encoding and decoding bytes."""

    codec_type = CodecType.BYTES.value

    def can_encode(self, value: typing.Any) -> bool:
        return isinstance(value, bytes)

    def can_decode(self, target_type: type[typing.Any]) -> bool:
        return target_type is bytes

    def encode(self, value: bytes) -> bytes:
        assert self.can_encode(value)
        return value

    def decode[T](self, data: bytes, target_type: type[T]) -> T:
        assert self.can_decode(target_type)
        return data  # type: ignore[return-value]


class StringCodec:
    """Codec for encoding and decoding strings."""

    codec_type = CodecType.STRING.value

    def can_encode(self, value: typing.Any) -> bool:
        return isinstance(value, str)

    def can_decode(self, target_type: type[typing.Any]) -> bool:
        return target_type is str

    def encode(self, value: str) -> bytes:
        assert self.can_encode(value)
        return value.encode()

    def decode[T](self, data: bytes, target_type: type[T]) -> T:
        assert self.can_decode(target_type)
        return data.decode()  # type: ignore[return-value]


class ProtobufCodec:
    """Codec for encoding and decoding protobuf messages."""

    codec_type = CodecType.PROTOBUF.value

    def can_encode(self, value: typing.Any) -> bool:
        return isinstance(value, Message)

    def can_decode(self, target_type: type[typing.Any]) -> bool:
        return issubclass(target_type, Message)

    def encode(self, value: Message) -> bytes:
        assert self.can_encode(value)
        return value.SerializeToString()

    def decode[T](self, data: bytes, target_type: type[T]) -> T:
        assert self.can_decode(target_type)
        return target_type.FromString(data)  # type: ignore[attr-defined, no-any-return]
