"""Cliente de chat - conecta ao servidor e troca mensagens."""

from __future__ import annotations


import argparse
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

from net.application.chat import decode
from net.application.chat.file import FileMessage
from net.application.chat.text import TextMessage
from net.application.ui import UI
from net.application.ui.impl import GUI, ConsoleUI
from net.logging import setup_logging
from net.stack.factory import (
    CLIENT_A_NAME,
    CLIENT_B_NAME,
    SERVER_VADDRESS,
    build_transport_layer,
)
from net.stack.transport import Connection

logger = logging.getLogger(__name__)


class Client:
    """Cliente de chat parametrizável com qualquer implementação de UI."""

    def __init__(
        self,
        name: str,
        other: str,
        ui: UI | None = None,
    ) -> None:
        """Inicializa o cliente e estabelece a conexão com o servidor.

        Args:
            name (str): Nome deste cliente (ex.: `"Alice"`).
            other (str): Nome do destinatário padrão (ex.: `"Bob"`).
            ui (ChatUI | None): Implementação de UI a usar.
        """
        self.name = name
        self.other = other
        self.ui: UI = ui if ui is not None else ConsoleUI()
        self.connection: Connection | None = None
        self.close_lock = threading.Lock()

    def run(self) -> None:
        """Mostra a UI imediatamente e conecta ao servidor em background."""
        self.ui.show_connecting(self.name)

        def _do_connect() -> None:
            transport = build_transport_layer(self.name)
            self.connection = transport.connect(SERVER_VADDRESS)
            threading.Thread(target=self._receive_loop, daemon=True).start()
            self.ui.show_connected(self.name)

        threading.Thread(target=_do_connect, daemon=True).start()

        try:
            while True:
                inp = self.ui.read_input()

                if inp is None:
                    break

                if self.connection is None:
                    continue

                if isinstance(inp, Path):
                    self.connection.send(
                        FileMessage(
                            sender=self.name,
                            recipient=self.other,
                            name=inp.name,
                            mime="application/octet-stream",
                            data=inp.read_bytes(),
                        ).encode()
                    )

                elif inp.strip():
                    self.connection.send(
                        TextMessage(
                            sender=self.name,
                            recipient=self.other,
                            content=inp.strip(),
                        ).encode()
                    )

        except (KeyboardInterrupt, EOFError):
            logger.info("[CHAT] Interrompido, encerrando conexão…")

        finally:
            self._close_connection()

    def _close_connection(self) -> None:
        """Fecha a conexão de forma idempotente e thread-safe."""
        with self.close_lock:
            connection = self.connection
            self.connection = None

        if connection is None:
            return

        try:
            connection.close()
        except Exception:
            pass

    def _receive_loop(self) -> None:
        assert self.connection is not None
        while True:
            raw = self.connection.receive()

            if raw is None:
                self.ui.show_server_disconnected()
                break

            try:
                message = decode(raw)

            except ValueError as exc:
                logger.warning("Mensagem inválida: %s", exc)
                continue

            self.ui.show_message(message, datetime.now())


def _auto_select_ui(force_gui: bool = False) -> UI:
    """Seleciona automaticamente a UI baseado em TTY ou flag --gui.

    Args:
        force_gui (bool): Se True, força o uso da GUI independente do TTY.

    Returns:
        UI: Instância de ConsoleUI ou GUI.
    """
    if force_gui or not sys.stdin.isatty():
        return GUI()
    return ConsoleUI()


def main_alice() -> None:
    """Ponto de entrada para Alice.

    Uso:
        alice           # Console (se TTY disponível)
        alice --gui     # Interface gráfica
    """
    parser = argparse.ArgumentParser(description="Cliente de chat Alice")
    parser.add_argument("--gui", action="store_true", help="Usar interface gráfica")
    args = parser.parse_args()

    setup_logging(level=logging.WARNING, show_date=False)
    ui = _auto_select_ui(force_gui=args.gui)
    Client(CLIENT_A_NAME, CLIENT_B_NAME, ui=ui).run()


def main_bob() -> None:
    """Ponto de entrada para Bob.

    Uso:
        bob           # Console (se TTY disponível)
        bob --gui     # Interface gráfica
    """
    parser = argparse.ArgumentParser(description="Cliente de chat Bob")
    parser.add_argument("--gui", action="store_true", help="Usar interface gráfica")
    args = parser.parse_args()

    setup_logging(level=logging.WARNING, show_date=False)
    ui = _auto_select_ui(force_gui=args.gui)
    Client(CLIENT_B_NAME, CLIENT_A_NAME, ui=ui).run()
