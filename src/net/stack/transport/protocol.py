"""Interfaces para a camada de transporte."""

from typing import Protocol, runtime_checkable

from net.model import VirtualAddress

TIMEOUT: float = 2.0


@runtime_checkable
class Connection(Protocol):
    """Interface para conexões de transporte."""

    def send(self, data: bytes) -> None:
        """Envia dados pela conexão.

        Args:
            data (bytes): Os dados a serem enviados.

        """
        ...

    def receive(self) -> bytes | None:
        """Recebe dados da conexão.

        Returns:
            bytes | None: Os dados recebidos, ou None se a conexão foi fechada.
        """
        ...

    def close(self) -> None:
        """Fecha a conexão."""
        ...


@runtime_checkable
class Transport(Protocol):
    """Interface para a camada de transporte."""

    def connect(self, destination: VirtualAddress) -> Connection:
        """Estabelece uma conexão com o endereço virtual de destino.

        Args:
            destination (VirtualAddress): O endereço virtual de destino.

        Returns:
            Connection: A conexão estabelecida.
        """
        ...

    def accept(self) -> Connection:
        """Aceita uma conexão de entrada.

        Returns:
            Connection: A conexão aceita.
        """
        ...
