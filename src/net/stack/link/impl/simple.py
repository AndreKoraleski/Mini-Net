"""Implementação simples da camada de enlace."""

from __future__ import annotations


import logging
from typing import cast

from net.base import Frame, Packet
from net.model import MACAddress, VirtualIPAddress
from net.stack.link import Link
from net.stack.physical import Physical

logger = logging.getLogger(__name__)


class SimpleLink(Link):
    """Implementação simples da camada de enlace."""

    def __init__(
        self,
        physical: Physical,
        local_mac: MACAddress,
        arp_table: dict[VirtualIPAddress, MACAddress],
    ) -> None:
        """Inicializa a camada de enlace.

        Como os requisitos de Checksum e verificação de CRC já estão implementados na
        estrutura de dados fornecida (Frame), esta implementação é direta e os
        requisitos 2 e 3 da Fase 4 do projeto já estão trivialmente atendidos.

        Args:
            physical (Physical): A camada física para enviar e receber dados.
            local_mac (MACAddress): O endereço MAC local desta camada de enlace.
            arp_table (dict[VirtualIPAddress, MACAddress]): A tabela ARP para resolução
                de endereços.
        """
        self.physical = physical
        self.local_mac = local_mac
        self.arp_table = arp_table

    def send(self, packet: Packet, destination: VirtualIPAddress) -> None:
        """Envia um pacote para o endereço virtual de destino.

        Args:
            packet (Packet): O pacote a ser enviado.
            destination (VirtualIPAddress): O endereço virtual de destino.

        Raises:
            LookupError: Se o endereço virtual não estiver na tabela ARP.
        """
        destination_mac = self.arp_table.get(destination)

        if destination_mac is None:
            logger.error(
                "[ENLACE] %s -> ?  VIP desconhecido na tabela ARP: %s",
                self.local_mac,
                destination,
            )
            raise LookupError(f"ARP falhou para VIP: {destination}")

        frame = Frame(
            src_mac=self.local_mac,
            dst_mac=destination_mac,
            pacote_dict=packet.to_dict(),
        )

        logger.debug(
            "[ENLACE] %s -> %s  Quadro enviado. (vip_origem=%s  vip_destino=%s)",
            self.local_mac,
            destination_mac,
            packet.src_vip,
            destination,
        )

        self.physical.send(frame.serializar())

    def receive(self) -> Packet | None:
        """Recebe um pacote da camada de enlace.

        Returns:
            Packet | None: O pacote recebido, ou None se descartado por erro de
                integridade.
        """
        data = self.physical.receive()

        if not data:
            return None

        frame_dict, valid = Frame.deserializar(data)

        if frame_dict is None:
            logger.warning(
                "[ENLACE] ? -> %s  Quadro descartado: dados nulos.", self.local_mac
            )
            return None

        if not valid:
            logger.warning(
                "[ENLACE] %s -> %s  Quadro descartado: erro de integridade (CRC).",
                frame_dict.get("src_mac", "?"),
                self.local_mac,
            )
            return None

        packet_dict = cast(dict[str, object], frame_dict["data"])

        packet = Packet(
            src_vip=cast(str, packet_dict["src_vip"]),
            dst_vip=cast(str, packet_dict["dst_vip"]),
            ttl=cast(int, packet_dict["ttl"]),
            segmento_dict=cast(dict[str, object], packet_dict["data"]),
        )

        logger.debug(
            "[ENLACE] %s -> %s  Quadro recebido. (vip_origem=%s  vip_destino=%s)",
            frame_dict["src_mac"],
            self.local_mac,
            packet.src_vip,
            packet.dst_vip,
        )

        return packet
