"""Protocolo de UI para o cliente de chat."""

from datetime import datetime
from pathlib import Path
from typing import Protocol

from net.application.chat.codec import Message


class UI(Protocol):
    """Contrato de interface para qualquer UI do cliente de chat.

    Qualquer objeto que implemente estes métodos pode ser passado ao
    `ChatClient`, sem precisar herdar desta classe.
    """

    def show_connecting(self, name: str) -> None:
        """Notifica que a conexão com o servidor está sendo estabelecida.

        Args:
            name (str): Nome do usuário que está conectando.
        """
        ...

    def show_connected(self, name: str) -> None:
        """Notifica que a conexão com o servidor foi estabelecida.

        Args:
            name (str): Nome do usuário conectado.
        """
        ...

    def show_message(self, message: Message, at: datetime) -> None:
        """Exibe uma mensagem recebida do servidor.

        Args:
            message (Message): A mensagem recebida.
            at (datetime): Instante em que a mensagem foi recebida.
        """
        ...

    def show_server_disconnected(self) -> None:
        """Notifica que o servidor encerrou a conexão."""
        ...

    def read_input(self) -> str | Path | None:
        """Lê uma entrada do usuário.

        Returns:
            str: texto a enviar como mensagem.
            Path: caminho de arquivo a transferir.
            None: encerra a sessão.
        """
        ...
