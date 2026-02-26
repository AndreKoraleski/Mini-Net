"""Servidor de chat - aceita conexões de Alice e Bob e retransmite mensagens."""

import contextlib
import logging
import threading
from typing import cast

from net.application.chat import decode
from net.application.chat.file import FileMessage
from net.application.chat.system import SystemMessage
from net.application.chat.text import TextMessage
from net.logging import setup_logging
from net.stack.factory import (
    CLIENT_A_NAME,
    CLIENT_A_VIP,
    CLIENT_B_NAME,
    CLIENT_B_VIP,
    SERVER_NAME,
    build_transport_layer,
)
from net.stack.transport import Connection
from net.stack.transport.impl import ReliableConnection

logger = logging.getLogger(__name__)

_VIP_TO_NAME = {
    CLIENT_A_VIP: CLIENT_A_NAME,
    CLIENT_B_VIP: CLIENT_B_NAME,
}


class Server:
    """Servidor de chat que retransmite mensagens entre clientes conectados."""

    def __init__(self) -> None:
        """Inicializa o servidor e a camada de transporte."""
        self.transport = build_transport_layer(SERVER_NAME)
        self.clients: dict[str, Connection] = {}
        self.lock = threading.Lock()
        self.shutting_down = False
        self.all_disconnected = threading.Event()

    def run(self) -> None:
        """Aceita conexões e despacha cada uma para uma thread dedicada."""
        logger.info("[CHAT] Servidor iniciado.")

        try:
            while True:
                connection = self.transport.accept()
                name = _VIP_TO_NAME.get(
                    cast(ReliableConnection, connection).remote_address.vip,
                    str(cast(ReliableConnection, connection).remote_address.vip),
                )
                with self.lock:
                    self.clients[name] = connection

                logger.info("[CHAT] %s conectou.", name)

                # Envia lista de usuários online para o novo cliente
                with self.lock:
                    online_users = [n for n in self.clients if n != name]
                if online_users:
                    online_list = ", ".join(online_users) + " entrou no chat."
                    connection.send(SystemMessage(online_list).encode())

                self._broadcast(SystemMessage(f"{name} entrou no chat."), exclude=name)

                threading.Thread(
                    target=self._handle,
                    args=(connection, name),
                    daemon=True,
                ).start()

        except KeyboardInterrupt:
            logger.info("[CHAT] Shutdown iniciado, notificando clientes…")
            self.shutting_down = True
            self._broadcast(SystemMessage("__SHUTDOWN__"))
            with self.lock:
                has_clients = bool(self.clients)
            if has_clients:
                self.all_disconnected.wait(timeout=30.0)
            logger.info("[CHAT] Servidor encerrado.")

    def _handle(self, connection: Connection, name: str) -> None:
        try:
            while True:
                raw = connection.receive()
                if raw is None:
                    break

                try:
                    message = decode(raw)

                except ValueError as exc:
                    logger.warning("[CHAT] Mensagem inválida de %s: %s", name, exc)
                    continue

                # Responde à solicitação de lista de usuários online
                if (
                    isinstance(message, SystemMessage)
                    and message.content == "__REQUEST_ONLINE__"
                ):
                    with self.lock:
                        online_users = [n for n in self.clients if n != name]
                    if online_users:
                        online_list = ", ".join(online_users) + " entrou no chat."
                        connection.send(SystemMessage(online_list).encode())
                    continue

                if isinstance(message, (TextMessage, FileMessage)):
                    logger.debug(
                        "[CHAT] %s -> %s",
                        name,
                        message.recipient,
                    )
                    with self.lock:
                        dest = self.clients.get(message.recipient)

                    if dest is not None:
                        dest.send(message.encode())

                    else:
                        logger.warning(
                            "[CHAT] Destinatário %r não conectado.", message.recipient
                        )

        except Exception as exc:
            logger.error("[CHAT] Erro na conexão de %s: %s", name, exc)

        finally:
            with self.lock:
                self.clients.pop(name, None)
                empty = not self.clients
            logger.info("[CHAT] %s desconectou.", name)
            if not self.shutting_down:
                self._broadcast(SystemMessage(f"{name} saiu do chat."))

            if empty:
                self.all_disconnected.set()

    def _broadcast(self, message: SystemMessage, exclude: str | None = None) -> None:
        with self.lock:
            targets = [
                connection
                for name, connection in self.clients.items()
                if name != exclude
            ]

        for connection in targets:
            with contextlib.suppress(Exception):
                connection.send(message.encode())


def main() -> None:
    """Ponto de entrada do servidor de chat."""
    setup_logging(level=logging.DEBUG)
    Server().run()
