import dataclasses
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

    from fastcc.codec_registry import CodecRegistry

from fastcc.constants import STATUS_CODE_SUCCESS
from fastcc.utilities import get_status_code


@dataclasses.dataclass(eq=False, match_args=False, kw_only=True, slots=True)
class Response[T]:
    """Response to a request.

    Parameters
    ----------
    value
        The value contained in the response.
    status_code
        The status code of the response, where a value of 0 indicates a
        successful operation and any non-zero value indicates an error.
    """

    value: T

    _: dataclasses.KW_ONLY
    status_code: int = STATUS_CODE_SUCCESS

    @classmethod
    def from_message(
        cls,
        message: aiomqtt.Message,
        target_type: type[T],
        *,
        codec_registry: CodecRegistry,
        codec_type: int | None = None,
    ) -> Response[T]:
        """Create a response from an MQTT message.

        Parameters
        ----------
        message
            The MQTT message to create the response from.
        target_type
            The type to decode the message payload into.
        codec_registry
            The codec registry to use for decoding the message payload.
        codec_type
            Force the use of a specific codec type for decoding.
            If ``None``, the first compatible codec in the registry
            will be used.

        Returns
        -------
        Response[T]
            The response created from the MQTT message.
        """
        try:
            status_code = get_status_code(message)
        except AttributeError:
            status_code = STATUS_CODE_SUCCESS

        value = codec_registry.decode(
            message.payload,
            target_type,
            codec_type=codec_type,
        )
        return cls(value=value, status_code=status_code)
