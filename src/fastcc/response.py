"""The response class."""

import dataclasses
import typing

if typing.TYPE_CHECKING:
    import aiomqtt

    from fastcc.codec import CodecRegistry

from fastcc.constants import STATUS_CODE_SUCCESS
from fastcc.serialization import default_registry, deserialize
from fastcc.utilities import get_status_code


@dataclasses.dataclass(frozen=True, slots=True)
class Response:
    """Represents a response to a request or stream.

    Attributes
    ----------
    packet
        The packet contained in the response.
    status_code
        The status code of the response.
    """

    packet: typing.Any
    status_code: int

    @classmethod
    def from_message(
        cls,
        message: aiomqtt.Message,
        codec_registry: CodecRegistry | None = None,
    ) -> Response:
        """Create a response from an MQTT message.

        Parameters
        ----------
        message
            The MQTT message to create the response from.
        codec_registry
            The codec registry to use for deserialization.
            If ``None``, the default registry will be used.

        Returns
        -------
        Response
            The response created from the MQTT message.
        """
        if codec_registry is None:
            codec_registry = default_registry

        try:
            status_code = get_status_code(message)
        except AttributeError:
            status_code = STATUS_CODE_SUCCESS

        packet = deserialize(message.payload, codec_registry)
        return cls(packet=packet, status_code=status_code)
