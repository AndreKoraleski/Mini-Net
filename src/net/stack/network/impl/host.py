"""Implementação da camada de rede para hosts finais."""

import logging
from typing import cast

from net.base import Packet, Segment
from net.model import VirtualIPAddress
from net.stack.link import Link
from net.stack.network import DEFAULT_TTL, Network

logger = logging.getLogger(__name__)


class HostNetwork(Network):
    """Camada de rede para hosts finais (Alice, Bob, Servidor)."""

    def __init__(
        self,
        link: Link,
        local_vip: VirtualIPAddress,
        routing_table: dict[VirtualIPAddress, VirtualIPAddress],
    ) -> None:
        """Inicializa a camada de rede para host.

        Args:
            link (Link): A camada de enlace subjacente.
            local_vip (VirtualIPAddress): O endereço virtual local.
            routing_table (dict[VirtualIPAddress, VirtualIPAddress]): Tabela de
                roteamento (tipicamente apenas o gateway padrão).
        """
        self.link = link
        self.local_vip = local_vip
        self.routing_table = routing_table

    def send(self, segment: Segment, destination: VirtualIPAddress) -> None:
        """Envia um segmento para o endereço virtual de destino.

        Args:
            segment (Segment): O segmento a ser enviado.
            destination (VirtualIPAddress): O endereço virtual de destino.

        Raises:
            LookupError: Se o destino não estiver na tabela de roteamento.
        """
        next_hop = self.routing_table.get(destination)

        if next_hop is None:
            logger.error(
                "[REDE] %s -> ?  Destino desconhecido na tabela de roteamento: %s",
                self.local_vip,
                destination,
            )
            raise LookupError(f"Roteamento falhou para VIP: {destination}")

        packet = Packet(
            src_vip=self.local_vip,
            dst_vip=destination,
            ttl=DEFAULT_TTL,
            segmento_dict=segment.to_dict(),
        )

        logger.debug(
            "[REDE] %s -> %s  Pacote enviado. (proximo_salto=%s  ttl=%d)",
            self.local_vip,
            destination,
            next_hop,
            packet.ttl,
        )

        self.link.send(packet, next_hop)

    def receive(self) -> Segment | None:
        """Recebe um segmento endereçado a este host.

        Bloqueia até que um pacote válido e destinado ao VIP local seja recebido.

        Returns:
            Segment | None: O segmento recebido, ou None se o pacote foi
                descartado (TTL expirado, integridade ou destino incorreto).
        """
        packet = self.link.receive()

        if packet is None:
            return None

        if packet.dst_vip != self.local_vip:
            logger.warning(
                "[REDE] %s -> %s  Pacote descartado: destino inesperado.",
                packet.src_vip,
                packet.dst_vip,
            )
            return None

        segment_dict = packet.data

        logger.debug(
            "[REDE] %s -> %s  Segmento entregue. (ttl=%d)",
            packet.src_vip,
            self.local_vip,
            packet.ttl,
        )

        return Segment(
            seq_num=cast(int, segment_dict["seq_num"]),
            is_ack=cast(bool, segment_dict["is_ack"]),
            payload=cast(dict[str, object], segment_dict["payload"]),
        )
