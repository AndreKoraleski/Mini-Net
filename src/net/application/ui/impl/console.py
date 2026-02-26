"""Implementação da UI de chat em console (stdin / stdout)."""

import threading
from datetime import datetime
from pathlib import Path

from net.application.chat.codec import Message
from net.application.chat.file import FileMessage
from net.application.chat.text import TextMessage
from net.stack.factory import DOWNLOADS_DIR, ensure_downloads_dir

FILE_COMMAND = "/file "


class ConsoleUI:
    """Implementação de `ChatUI` em console (stdin / stdout).

    Comandos de envio no stdin:
        - Texto simples -> envia `TextMessage`.
        - `/file <caminho>` -> envia `FileMessage` com o arquivo indicado.
    """

    def show_connecting(self, name: str) -> None:
        """Exibe mensagem de aguarde no terminal.

        Args:
            name (str): Nome do usuário que está conectando.
        """
        print(f"Conectando como {name}…")

    def show_connected(self, name: str) -> None:
        """Exibe a mensagem de boas-vindas no terminal.

        Args:
            name (str): Nome do usuário conectado.
        """
        print(f"Conectado como {name}. Escreva e pressione Enter.")
        print(f"Para enviar arquivo: {FILE_COMMAND}<caminho>")
        print("Ctrl+C para sair.\n")

    def show_message(self, message: Message, at: datetime) -> None:
        """Imprime a mensagem formatada no terminal.

        Args:
            message (Message): A mensagem recebida.
            at (datetime): Instante em que a mensagem foi recebida.
        """
        timestamp = at.strftime("%H:%M:%S")

        if isinstance(message, TextMessage):
            print(f"\r[{timestamp}] {message.sender}: {message.content}")

        elif isinstance(message, FileMessage):
            # Salvar em thread separada - não bloqueia o loop de recepção.
            threading.Thread(
                target=self._save_file,
                args=(message, timestamp),
                daemon=True,
            ).start()

        else:
            print(f"\r[{timestamp}] [SISTEMA] {message.content}")

    def show_server_disconnected(self) -> None:
        """Imprime mensagem de desconexão no terminal."""
        print("\n[SISTEMA] Conexão encerrada pelo servidor.")

    def read_input(self) -> str | Path | None:
        """Lê uma linha do stdin.

        Returns:
            str | Path | None: Texto a enviar, caminho de arquivo, ou None para
                encerrar.
        """
        try:
            line = input()

        except KeyboardInterrupt, EOFError:
            print("\nEncerrando...")
            return None

        if line.startswith(FILE_COMMAND):
            path = Path(line[len(FILE_COMMAND) :].strip())
            if not path.is_file():
                print(f"[ERRO] Arquivo não encontrado: {path}")
                return ""
            return path

        return line

    @staticmethod
    def _save_file(message: FileMessage, timestamp: str) -> None:
        """Salva o arquivo recebido em downloads/<destinatário>/<nome>.

        Args:
            message (FileMessage): A mensagem de arquivo recebida.
            timestamp (str): Horário formatado da recepção.
        """
        destination = DOWNLOADS_DIR / message.recipient / message.name
        ensure_downloads_dir()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(message.data)
        print(
            f"\r[{timestamp}] {message.sender} enviou arquivo: "
            f"{message.name} ({message.size} B) - salvo em {destination.resolve()}"
        )
