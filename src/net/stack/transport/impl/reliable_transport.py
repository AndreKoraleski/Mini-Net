"""Implementação do multiplexador de transporte confiável."""

import logging
import queue
import threading

from net.base import Segment
from net.model import VirtualAddress, VirtualIPAddress
from net.model.address import Port
from net.stack.network import Network
from net.stack.transport import Connection, Transport
from net.stack.transport.impl.reliable_connection import ReliableConnection

logger = logging.getLogger(__name__)

type ConnectionKey = tuple[VirtualIPAddress, Port, Port]


class ReliableTransport(Transport):
    """Multiplexador de transporte confiável Stop-and-Wait."""

    def __init__(
        self,
        network: Network,
        local_address: VirtualAddress,
    ) -> None:
        """Inicializa o transport e arranca o loop de despacho em background.

        Args:
            network (Network): Camada de rede subjacente.
            local_address (VirtualAddress): Endereço virtual local.
        """
        self.network = network
        self.local_address = local_address
        self.connections: dict[ConnectionKey, ReliableConnection] = {}
        self.lock = threading.Lock()
        self.accept_queue: queue.Queue[ReliableConnection] = queue.Queue()
        self.thread = threading.Thread(
            target=self._dispatch_loop,
            name=f"transport-{local_address}",
            daemon=True,
        )
        self.thread.start()
        logger.debug("[TRANSPORTE] %s  Loop de despacho iniciado.", self.local_address)

    def connect(self, destination: VirtualAddress) -> Connection:
        """Estabelece uma conexão com o endereço virtual de destino.

        Args:
            destination (VirtualAddress): Endereço virtual do destino.

        Returns:
            Connection: A conexão estabelecida.
        """
        key: ConnectionKey = (
            destination.vip,
            destination.port,
            self.local_address.port,
        )
        connection = ReliableConnection(
            network=self.network,
            local_address=self.local_address,
            remote_address=destination,
            on_close=lambda: self._remove(key),
        )
        with self.lock:
            self.connections[key] = connection

        logger.debug(
            "[TRANSPORTE] %s -> %s  Conexão estabelecida.",
            self.local_address,
            destination,
        )
        return connection

    def accept(self) -> Connection:
        """Bloqueia até receber uma conexão de entrada e a retorna.

        Returns:
            Connection: A conexão aceita.
        """
        connection = self.accept_queue.get()
        logger.debug(
            "[TRANSPORTE] %s  Conexão aceita de %s.",
            self.local_address,
            connection.remote_address,
        )
        return connection

    def _remove(self, key: ConnectionKey) -> None:
        with self.lock:
            self.connections.pop(key, None)

        logger.debug(
            "[TRANSPORTE] %s  Conexão removida. (chave=%s)",
            self.local_address,
            key,
        )

    def _dispatch_loop(self) -> None:
        while True:
            segment = self.network.receive()

            if segment is None:
                continue

            self._route(segment)

    def _route(self, segment: Segment) -> None:
        remote_vip = VirtualIPAddress(str(segment.payload["src_ip"]))
        remote_port = Port(int(str(segment.payload["src_port"])))
        local_port = Port(int(str(segment.payload["dst_port"])))
        key: ConnectionKey = (remote_vip, remote_port, local_port)

        with self.lock:
            conn = self.connections.get(key)

        if conn is not None:
            conn.dispatch(segment)
            return

        # Segmento inesperado sem conexão registrada - descartar ACKs e FINs
        if segment.is_ack or segment.payload.get("fin"):
            logger.debug(
                "[TRANSPORTE] %s  Segmento descartado (sem conexão). (src=%s:%d)",
                self.local_address,
                remote_vip,
                remote_port,
            )
            return

        # Primeiro segmento de uma nova conexão de entrada
        remote_address = VirtualAddress(remote_vip, remote_port)
        new_connection = ReliableConnection(
            network=self.network,
            local_address=self.local_address,
            remote_address=remote_address,
            on_close=lambda: self._remove(key),
        )
        with self.lock:
            self.connections[key] = new_connection

        new_connection.dispatch(segment)
        self.accept_queue.put(new_connection)
        logger.debug(
            "[TRANSPORTE] %s  Nova conexão de %s:%d.",
            self.local_address,
            remote_vip,
            remote_port,
        )
