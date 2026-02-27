"""Implementação de uma conexão confiável."""

from __future__ import annotations


import base64
import logging
import queue
import threading
import time
from collections.abc import Callable

from net.base import Segment
from net.model import VirtualAddress
from net.stack.network import Network
from net.stack.transport import TIMEOUT, Connection

logger = logging.getLogger(__name__)

MSS: int = 4096
MAX_FIN_RETRIES: int = 8


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
        self.syn_ack_queue: queue.Queue[Segment] = queue.Queue()
        self.fin_queue: queue.Queue[int] = queue.Queue()
        self.data_queue: queue.Queue[Segment | None] = queue.Queue()
        self.connected: bool = False
        self.closed: bool = False
        self.close_lock = threading.Lock()
        self.send_lock = threading.Lock()

    def connect(self) -> None:
        """Lado ativo do handshake de 3 vias (SYN / SYN-ACK / ACK)."""
        syn = Segment(
            seq_num=0,
            is_ack=False,
            payload={
                "src_ip": self.local_address.vip,
                "src_port": self.local_address.port,
                "dst_port": self.remote_address.port,
                "data": "",
                "syn": True,
                "more": False,
            },
        )

        while True:
            self.network.send(syn, self.remote_address.vip)
            logger.debug(
                "[TRANSPORTE] %s -> %s  SYN enviado.",
                self.local_address,
                self.remote_address,
            )
            try:
                self.syn_ack_queue.get(timeout=TIMEOUT)
                break

            except queue.Empty:
                logger.warning(
                    "[TRANSPORTE] %s -> %s  Timeout aguardando SYN-ACK, retransmitindo SYN.",
                    self.local_address,
                    self.remote_address,
                )

        # Envia ACK do SYN-ACK
        self.connected = True
        self._send_ack(0)
        logger.debug(
            "[TRANSPORTE] %s -> %s  Handshake concluído (ativo).",
            self.local_address,
            self.remote_address,
        )

    def accept(self) -> None:
        """Lado passivo do handshake de 3 vias.)"""
        # Consome o SYN que dispatch() colocou em data_queue
        item = self.data_queue.get()
        assert item is not None and item.payload.get("syn"), "Esperado SYN inicial"

        syn_ack = Segment(
            seq_num=0,
            is_ack=True,
            payload={
                "src_ip": self.local_address.vip,
                "src_port": self.local_address.port,
                "dst_port": self.remote_address.port,
                "data": "",
                "syn": True,
                "more": False,
            },
        )

        while True:
            self.network.send(syn_ack, self.remote_address.vip)
            logger.debug(
                "[TRANSPORTE] %s -> %s  SYN-ACK enviado.",
                self.local_address,
                self.remote_address,
            )
            try:
                self.ack_queue.get(timeout=TIMEOUT)
                break

            except queue.Empty:
                logger.warning(
                    "[TRANSPORTE] %s -> %s  Timeout aguardando ACK do SYN-ACK, retransmitindo.",
                    self.local_address,
                    self.remote_address,
                )

        self.connected = True
        logger.debug(
            "[TRANSPORTE] %s  Handshake concluído (passivo).",
            self.local_address,
        )

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

        with self.send_lock:
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

        try:
            while True:
                segment = self._receive_chunk()
                buffer += base64.b64decode(str(segment.payload["data"]))

                if not segment.payload.get("more", False):
                    break

        except EOFError:
            return None

        logger.debug(
            "[TRANSPORTE] %s  %d byte(s) recebidos.",
            self.local_address,
            len(buffer),
        )
        return bytes(buffer)

    def abort(self) -> None:
        """Encerra a conexão imediatamente, sem handshake, desbloqueando threads em espera."""
        with self.close_lock:
            if self.closed:
                return
            self.closed = True

        self.data_queue.put(None)
        self.ack_queue.put_nowait(
            type(
                "_Abort",
                (),
                {"sequence_number": self.send_sequence},
            )()
        )
        self.fin_queue.put(-1)

        if self.on_close is not None:
            self.on_close()

        logger.debug(
            "[TRANSPORTE] %s -> %s  Conexão abortada.",
            self.local_address,
            self.remote_address,
        )

    def close(self) -> None:
        """Encerra a conexão com o handshake de 4 passos (FIN/ACK/FIN/ACK)."""
        with self.close_lock:
            if self.closed:
                return
            self.closed = True

        passive = not self.fin_queue.empty()

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

        # Enviar FIN e aguardar ACK (até MAX_FIN_RETRIES tentativas)
        for attempt in range(1, MAX_FIN_RETRIES + 1):
            self.network.send(fin, self.remote_address.vip)
            logger.debug(
                "[TRANSPORTE] %s -> %s  FIN enviado. (seq=%d, tentativa=%d/%d)",
                self.local_address,
                self.remote_address,
                self.send_sequence,
                attempt,
                MAX_FIN_RETRIES,
            )
            try:
                ack = self.ack_queue.get(timeout=TIMEOUT)
                if ack.sequence_number == self.send_sequence:
                    logger.debug(
                        "[TRANSPORTE] %s -> %s  ACK do FIN recebido.",
                        self.local_address,
                        self.remote_address,
                    )
                    break
            except queue.Empty:
                if attempt == MAX_FIN_RETRIES:
                    logger.warning(
                        "[TRANSPORTE] %s -> %s  Limite de retransmissões do FIN atingido, desistindo.",
                        self.local_address,
                        self.remote_address,
                    )
                else:
                    logger.warning(
                        "[TRANSPORTE] %s -> %s  Timeout aguardando ACK do FIN, retransmitindo.",
                        self.local_address,
                        self.remote_address,
                    )

        if passive:
            logger.debug(
                "[TRANSPORTE] %s -> %s  Conexão encerrada (fechamento passivo).",
                self.local_address,
                self.remote_address,
            )
            if self.on_close is not None:
                self.on_close()
            return

        # Aguardar FIN do peer
        logger.debug(
            "[TRANSPORTE] %s  Aguardando FIN do peer (FIN_WAIT_2)…",
            self.local_address,
        )
        self.fin_queue.get()  # Bloqueia até o FIN chegar
        logger.debug(
            "[TRANSPORTE] %s -> %s  Conexão encerrada (4-way FIN).",
            self.local_address,
            self.remote_address,
        )

        if self.on_close is not None:
            self.on_close()

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

        Roteamento:
        - SYN puro (is_ack=False, syn=True)  -> data_queue    (consumido por accept())
        - SYN-ACK  (is_ack=True,  syn=True)  -> syn_ack_queue (consumido por connect())
        - ACK puro de SYN (is_ack=True, syn=True sem dados)  -> ack_queue (handshake passivo)
        - FIN      (fin=True)                -> ACK imediato + fin_queue + data_queue=None
        - ACK de dados/FIN                   -> ack_queue
        - Dados                              -> data_queue

        Args:
            segment (Segment): O segmento a ser encaminhado.
        """
        if segment.payload.get("fin"):
            self._send_ack(segment.sequence_number)
            logger.debug(
                "[TRANSPORTE] %s  FIN recebido. ACK enviado.",
                self.local_address,
            )
            self.fin_queue.put(segment.sequence_number)
            self.data_queue.put(None)
            return

        if segment.payload.get("syn"):
            if segment.is_ack:
                if self.connected:
                    logger.debug(
                        "[TRANSPORTE] %s  SYN-ACK retransmitido, reenviando ACK.",
                        self.local_address,
                    )
                    self._send_ack(0)
                else:
                    logger.debug(
                        "[TRANSPORTE] %s  SYN-ACK recebido.",
                        self.local_address,
                    )
                    self.syn_ack_queue.put(segment)
            else:
                if self.connected:
                    logger.debug(
                        "[TRANSPORTE] %s  SYN duplicado descartado (já conectado).",
                        self.local_address,
                    )
                else:
                    logger.debug(
                        "[TRANSPORTE] %s  SYN recebido.",
                        self.local_address,
                    )
                    self.data_queue.put(segment)
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
            item = self.data_queue.get()

            if item is None:
                raise EOFError

            segment = item

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
