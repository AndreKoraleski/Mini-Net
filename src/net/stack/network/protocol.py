"""Interface de protocolo de rede."""

from typing import Protocol, runtime_checkable

from net.base import Segment
from net.model import VirtualIPAddress

DEFAULT_TTL: int = 64


@runtime_checkable
class Network(Protocol):
    """Interface para a camada de rede."""

    def send(self, segment: Segment, destination: VirtualIPAddress) -> None:
        """Envia um segmento para o endereço virtual de destino.

        Args:
            segment (Segment): O segmento a ser enviado.
            destination (VirtualIPAddress): O endereço virtual de destino.
        """
        ...

    def receive(self) -> Segment | None:
        """Recebe um segmento da camada de rede.

        Returns:
            Segment | None: O segmento recebido, ou None se descartado por
                erro de integridade.
        """
        ...
