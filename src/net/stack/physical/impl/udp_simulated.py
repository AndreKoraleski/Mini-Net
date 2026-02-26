"""Implementação de uma camada física simulada usando UDP."""

import json
import logging
import socket

from net.base import send_over_noisy_channel
from net.model import Address, MACAddress
from net.stack.physical import Physical

_ENCODING: str = "utf-8"
_UDP_BUFFER_SIZE: int = 65507

logger = logging.getLogger(__name__)


class UDPSimulated(Physical):
    """Camada física simulada usando UDP."""

    def __init__(
        self, sock: socket.socket, mac_table: dict[MACAddress, Address]
    ) -> None:
        """Camada física simulada usando UDP.

        Args:
            sock (socket.socket): O socket UDP para enviar e receber dados.
            mac_table (dict[MACAddress, Address]): Tabela de mapeamento de MAC para
                endereços IP e portas.
        """
        self.sock = sock
        self.mac_table = mac_table

    @property
    def _local_address(self) -> str:
        """Endereço local do socket no formato host:port."""
        try:
            host, port = self.sock.getsockname()
            return f"{host}:{port}"

        except OSError:
            return "<unbound>"

    def send(self, data: bytes) -> None:
        """Envia dados pela camada física simulada usando UDP.

        Args:
            data (bytes): Os dados a serem enviados.
        """
        if len(data) > _UDP_BUFFER_SIZE:
            raise ValueError(f"Dados muito grandes para UDP: {len(data)}.")

        try:
            frame_dict = json.loads(data.decode(_ENCODING))
            destination_mac = MACAddress(frame_dict["dst_mac"])
            source_mac = frame_dict.get("src_mac", "?")

        except Exception as e:
            logger.error("[FISICA] Quadro para envio inválido: %s", e)
            return

        destination_address = self.mac_table.get(destination_mac)

        if destination_address is None:
            logger.error("[FISICA] MAC desconhecido na tabela: %s", destination_mac)
            return

        destination_str = f"{destination_address.ip}:{destination_address.port}"
        logger.debug(
            "[FISICA] %s -> %s  Quadro enviado. (src_mac=%s  dst_mac=%s  tamanho=%d bytes)",  # noqa: E501
            self._local_address,
            destination_str,
            source_mac,
            destination_mac,
            len(data),
        )

        send_over_noisy_channel(
            self.sock,
            data,
            (destination_address.ip, destination_address.port),
        )

    def receive(self) -> bytes:
        """Recebe dados da camada física simulada usando UDP.

        Returns:
            bytes: Os dados recebidos.
        """
        try:
            data, (src_host, src_port) = self.sock.recvfrom(_UDP_BUFFER_SIZE)
            logger.debug(
                "[FISICA] %s:%d -> %s  Quadro recebido. (tamanho=%d bytes)",
                src_host,
                src_port,
                self._local_address,
                len(data),
            )
            return data

        except Exception as e:
            logger.error("[FISICA] Erro ao receber dados: %s", e)
            return b""
