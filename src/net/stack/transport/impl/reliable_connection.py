"""Implementação de uma conexão confiável."""

import base64
import logging
import queue
import time
from collections.abc import Callable

from net.base import Segment
from net.model import VirtualAddress
from net.stack.network import Network
from net.stack.transport import TIMEOUT, Connection

logger = logging.getLogger(__name__)

MSS: int = 1024


class ReliableConnection(Connection):
    """Conexão confiável Stop-and-Wait sobre a camada de rede."""

    def __init__(
        self,
        network: Network,
        local_address: VirtualAddress,
        remote_address: VirtualAddress,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        """Inicializa a conexão com os endereços locais e remotos.

        Args:
            network (Network): Camada de rede subjacente.
            local_address (VirtualAddress): Endereço virtual local.
            remote_address (VirtualAddress): Endereço virtual do destino.
            on_close (Callable[[], None] | None): Chamado ao encerrar a conexão.
        """
        self.network = network
        self.local_address = local_address
        self.remote_address = remote_address
        self.on_close = on_close
        self.send_sequence = 0
        self.receive_sequence = 0
        self.ack_queue: queue.Queue[Segment] = queue.Queue()
        self.data_queue: queue.Queue[Segment] = queue.Queue()

    def send(self, data: bytes) -> None:
        """Envia dados de forma confiável, fragmentando em MSS e aguardando ACKs.

        Args:
            data (bytes): Os dados a serem enviados.
        """
        logger.debug(
            "[TRANSPORTE] %s -> %s  Enviando %d byte(s).",
            self.local_address,
            self.remote_address,
            len(data),
        )
        chunks = [data[i : i + MSS] for i in range(0, max(1, len(data)), MSS)]

        for i, chunk in enumerate(chunks):
            more: bool = i < len(chunks) - 1
            self._send_chunk(chunk, more=more)

    def receive(self) -> bytes | None:
        """Recebe dados de forma confiável, reagrupando fragmentos.

        Returns:
            bytes | None: Os dados recebidos, ou None se a conexão foi fechada.
        """
        logger.debug("[TRANSPORTE] %s  Aguardando dados...", self.local_address)
        buffer = bytearray()

        while True:
            segment = self._receive_chunk()
            buffer += base64.b64decode(str(segment.payload["data"]))

            if not segment.payload.get("more", False):
                break

        logger.debug(
            "[TRANSPORTE] %s  %d byte(s) recebidos.",
            self.local_address,
            len(buffer),
        )
        return bytes(buffer)

    def close(self) -> None:
        """Encerra a conexão enviando um FIN e aguardando o ACK."""
        fin = Segment(
            seq_num=self.send_sequence,
            is_ack=False,
            payload={
                "src_ip": self.local_address.vip,
                "src_port": self.local_address.port,
                "dst_port": self.remote_address.port,
                "data": "",
                "fin": True,
                "more": False,
            },
        )

        while True:
            self.network.send(fin, self.remote_address.vip)
            logger.debug(
                "[TRANSPORTE] %s -> %s  FIN enviado. (seq=%d)",
                self.local_address,
                self.remote_address,
                self.send_sequence,
            )
            deadline = time.time() + TIMEOUT

            while time.time() < deadline:
                try:
                    ack = self.ack_queue.get(timeout=deadline - time.time())

                except queue.Empty:
                    break

                if ack.sequence_number == self.send_sequence:
                    logger.debug(
                        "[TRANSPORTE] %s -> %s  Conexão encerrada.",
                        self.local_address,
                        self.remote_address,
                    )
                    if self.on_close is not None:
                        self.on_close()
                    return

            logger.warning(
                "[TRANSPORTE] %s -> %s  Timeout aguardando ACK do FIN, retransmitindo.",
                self.local_address,
                self.remote_address,
            )

    def _send_ack(self, ack_sequence: int) -> None:
        """Envia um ACK para o número de sequência especificado.

        Args:
            ack_sequence (int): O número de sequência a ser ACKed.
        """
        ack = Segment(
            seq_num=ack_sequence,
            is_ack=True,
            payload={
                "src_ip": self.local_address.vip,
                "src_port": self.local_address.port,
                "dst_port": self.remote_address.port,
                "data": "",
                "more": False,
            },
        )
        self.network.send(ack, self.remote_address.vip)
        logger.debug(
            "[TRANSPORTE] %s -> %s  ACK enviado. (seq=%d)",
            self.local_address,
            self.remote_address,
            ack_sequence,
        )

    def _send_chunk(self, chunk: bytes, *, more: bool) -> None:
        """Envia um fragmento de dados com o número de sequência atual e aguarda o ACK.

        Args:
            chunk (bytes): O fragmento de dados a ser enviado.
            more (bool): Indica se há mais fragmentos a serem enviados após este.
        """
        segment = Segment(
            seq_num=self.send_sequence,
            is_ack=False,
            payload={
                "src_ip": self.local_address.vip,
                "src_port": self.local_address.port,
                "dst_port": self.remote_address.port,
                "data": base64.b64encode(chunk).decode(),
                "more": more,
            },
        )

        while True:
            self.network.send(segment, self.remote_address.vip)
            deadline = time.time() + TIMEOUT

            while time.time() < deadline:
                try:
                    ack_sequence = self.ack_queue.get(timeout=deadline - time.time())

                # Retransmitir se o timeout expirar sem receber o ACK esperado
                except queue.Empty:
                    break

                if ack_sequence.sequence_number == self.send_sequence:
                    logger.debug(
                        "[TRANSPORTE] %s -> %s  Chunk confirmado. (seq=%d)",
                        self.local_address,
                        self.remote_address,
                        self.send_sequence,
                    )
                    self.send_sequence ^= 1
                    return

                # Descartar ACKs duplicados ou fora de ordem
                logger.debug(
                    "[TRANSPORTE] %s  ACK duplicado descartado. (recebido=%d esperado=%d)",  # noqa: E501
                    self.local_address,
                    ack_sequence.sequence_number,
                    self.send_sequence,
                )

            logger.warning(
                "[TRANSPORTE] %s -> %s  Timeout, retransmitindo. (seq=%d)",
                self.local_address,
                self.remote_address,
                self.send_sequence,
            )

    def dispatch(self, segment: Segment) -> None:
        """Encaminha um segmento recebido para a fila correta desta conexão.

        Chamado pelo ReliableTransport para cada segmento destinado a esta conexão.
        FINs do lado remoto são respondidos com ACK e disparam o callback on_close.

        Args:
            segment (Segment): O segmento a ser encaminhado.
        """
        if segment.payload.get("fin"):
            self._send_ack(segment.sequence_number)
            logger.debug(
                "[TRANSPORTE] %s  FIN recebido. Encerrando conexão.",
                self.local_address,
            )
            if self.on_close is not None:
                self.on_close()
            return

        if segment.is_ack:
            logger.debug(
                "[TRANSPORTE] %s  ACK despachado. (seq=%d)",
                self.local_address,
                segment.sequence_number,
            )
            self.ack_queue.put(segment)

        else:
            logger.debug(
                "[TRANSPORTE] %s  Dados despachados. (seq=%d)",
                self.local_address,
                segment.sequence_number,
            )
            self.data_queue.put(segment)

    def _receive_chunk(self) -> Segment:
        """Recebe um fragmento de dados, aguardando o número de sequência esperado.

        Returns:
            Segment: O segmento recebido com o número de sequência esperado.
        """
        while True:
            segment = self.data_queue.get()

            if segment.sequence_number != self.receive_sequence:
                logger.debug(
                    "[TRANSPORTE] %s  Duplicata descartada. (recebido=%d esperado=%d)",
                    self.local_address,
                    segment.sequence_number,
                    self.receive_sequence,
                )
                self._send_ack(self.receive_sequence ^ 1)
                continue

            self._send_ack(segment.sequence_number)
            self.receive_sequence ^= 1
            logger.debug(
                "[TRANSPORTE] %s  Chunk aceito. (seq=%d)",
                self.local_address,
                segment.sequence_number,
            )
            return segment
