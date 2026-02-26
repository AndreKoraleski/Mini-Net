"""Implementação da camada de rede para roteadores."""

import dataclasses
import logging
import queue
import threading

from net.base import Packet, Segment
from net.model import VirtualIPAddress
from net.stack.link import Link
from net.stack.network import DEFAULT_TTL, Network

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class RouterStats:
    """Estatísticas de operação do roteador."""

    forwarded: int
    dropped_ttl: int
    dropped_unknown: int

    @property
    def total(self) -> int:
        """Total de pacotes processados."""
        return self.forwarded + self.dropped_ttl + self.dropped_unknown


class RouterNetwork(Network):
    """Camada de rede para roteadores.

    Uma thread dedicada bloqueia em `link.receive()` e enfileira pacotes
    recebidos. `receive()` consome da fila, decrementa o TTL, consulta a
    tabela de roteamento e encaminha via enlace.

    Como roteadores não são destinos finais, `receive()` sempre retorna
    `None`. Logo, o encaminhamento é um efeito colateral da chamada.
    """

    def __init__(
        self,
        link: Link,
        local_vip: VirtualIPAddress,
        routing_table: dict[VirtualIPAddress, VirtualIPAddress],
    ) -> None:
        """Inicializa a camada de rede para roteador.

        Inicia automaticamente a thread de recepção.

        Args:
            link (Link): A camada de enlace subjacente.
            local_vip (VirtualIPAddress): O endereço virtual local do roteador.
            routing_table (dict[VirtualIPAddress, VirtualIPAddress]): Tabela de
                roteamento completa (todos os destinos conhecidos).
        """
        self.link = link
        self.local_vip = local_vip
        self.routing_table = routing_table
        self._packet_queue: queue.Queue[Packet] = queue.Queue()
        self._forwarded = 0
        self._dropped_ttl = 0
        self._dropped_unknown = 0

        threading.Thread(
            target=self._receive_into_queue,
            name=f"router-recv-{local_vip}",
            daemon=True,
        ).start()

    def _receive_into_queue(self) -> None:
        """Bloqueia no enlace e enfileira pacotes recebidos."""
        while True:
            packet = self.link.receive()
            if packet is not None:
                self._packet_queue.put(packet)

    @property
    def stats(self) -> RouterStats:
        """Retorna um snapshot das estatísticas de operação."""
        return RouterStats(
            forwarded=self._forwarded,
            dropped_ttl=self._dropped_ttl,
            dropped_unknown=self._dropped_unknown,
        )

    def send(self, segment: Segment, destination: VirtualIPAddress) -> None:
        """Envia um segmento originado pelo próprio roteador.

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
        """Processa o próximo pacote da fila e o encaminha.

        Bloqueia até que haja um pacote na fila interna.

        Returns:
            None: Roteadores não entregam segmentos à camada de aplicação.
        """
        packet = self._packet_queue.get()

        if packet.ttl <= 0:
            logger.warning(
                "[REDE] %s -> %s  Pacote descartado: TTL expirado.",
                packet.src_vip,
                packet.dst_vip,
            )
            self._dropped_ttl += 1
            self._packet_queue.task_done()
            return None

        packet.ttl -= 1

        next_hop = self.routing_table.get(VirtualIPAddress(packet.dst_vip))

        if next_hop is None:
            logger.error(
                "[REDE] %s -> ?  Destino desconhecido na tabela de roteamento: %s",
                packet.src_vip,
                packet.dst_vip,
            )
            self._dropped_unknown += 1
            self._packet_queue.task_done()
            return None

        logger.debug(
            "[REDE] %s -> %s  Pacote encaminhado. (proximo_salto=%s  ttl=%d)",
            packet.src_vip,
            packet.dst_vip,
            next_hop,
            packet.ttl,
        )

        self.link.send(packet, next_hop)
        self._forwarded += 1
        self._packet_queue.task_done()
        return None
