import typing

if typing.TYPE_CHECKING:
    from fastcc.codecs import Codec

from fastcc.codecs import BytesCodec, ProtobufCodec, StringCodec
from fastcc.exceptions import CodecError, CodecNotFoundError


class CodecRegistry:
    """Registry for codecs that can parse values to and from bytes."""

    def __init__(self) -> None:
        self._codecs_by_type: dict[int, Codec] = {}
        self._codecs_in_order: list[Codec] = []

    def register(self, codec: Codec, *, overwrite: bool = False) -> None:
        """Add a codec to the registry.

        Parameters
        ----------
        codec
            The codec to register.
        overwrite
            Whether to overwrite an existing codec of the same type.

        Raises
        ------
        ValueError
            If a codec of the same type is already registered and
            ``overwrite`` is ``False``.
        """
        if codec.codec_type in self._codecs_by_type:
            if not overwrite:
                error_message = (
                    f"Codec type {codec.codec_type!r} is already "
                    f"registered. Use overwrite to replace it."
                )
                raise ValueError(error_message)

            old = self._codecs_by_type[codec.codec_type]
            self._codecs_in_order.remove(old)

        self._codecs_by_type[codec.codec_type] = codec
        self._codecs_in_order.append(codec)

    def encode(
        self,
        value: typing.Any,
        *,
        codec_type: int | None = None,
    ) -> bytes:
        """Encode a value.

        Parameters
        ----------
        value
            The value to encode.
        codec_type
            Force the use of a specific codec type for encoding.
            If ``None``, the first compatible codec in the registry
            will be used.

        Returns
        -------
        bytes
            The encoded value.

        Raises
        ------
        CodecNotFoundError
            When ``codec_type`` is not ``None`` and no codec with the
            specified type is found in the registry.
        CodecError
            When ``codec_type`` is not ``None`` and the requested codec
            is not able to encode the value or when ``codec_type`` is
            ``None`` and no compatible codec is found for the value.
        """
        if codec_type is not None:
            if (selected := self._codecs_by_type.get(codec_type)) is None:
                raise CodecNotFoundError(codec_type)

            if not selected.can_encode(value):
                error_message = (
                    f"Requested codec with type {codec_type} cannot "
                    f"encode value: {value!r}"
                )
                raise CodecError(error_message)

            return selected.encode(value)

        for codec in self._codecs_in_order:
            if codec.can_encode(value):
                return codec.encode(value)

        error_message = f"No compatible codec found for value: {value!r}"
        raise CodecError(error_message)

    def decode[T](
        self,
        data: bytes,
        target_type: type[T],
        *,
        codec_type: int | None = None,
    ) -> T:
        """Decode data into a value of ``target_type``.

        Parameters
        ----------
        data
            The data to decode.
        target_type
            The type to decode the data into.
        codec_type
            Force the use of a specific codec type for decoding.
            If ``None``, the first compatible codec in the registry
            will be used.

        Returns
        -------
        T
            The decoded value.

        Raises
        ------
        CodecNotFoundError
            When ``codec_type`` is not ``None`` and no codec with the
            specified type is found in the registry.
        CodecError
            When ``codec_type`` is not ``None`` and the requested codec
            is not able to decode the value into ``target_type`` or
            when ``codec_type`` is ``None`` and no compatible codec is
            found for the ``target_type``.
        """
        if codec_type is not None:
            if (selected := self._codecs_by_type.get(codec_type)) is None:
                raise CodecNotFoundError(codec_type)

            if not selected.can_decode(target_type):
                error_message = (
                    f"Requested codec with type {codec_type} cannot "
                    f"decode data into target type {target_type!r}"
                )
                raise CodecError(error_message)

            return selected.decode(data, target_type)

        for codec in self._codecs_in_order:
            if codec.can_decode(target_type):
                return codec.decode(data, target_type)

        error_message = (
            f"No compatible codec found for target type {target_type!r}"
        )
        raise CodecError(error_message)


def _build_default_registry() -> CodecRegistry:
    registry = CodecRegistry()
    registry.register(BytesCodec())
    registry.register(StringCodec())
    registry.register(ProtobufCodec())
    return registry


default_codec_registry = _build_default_registry()
