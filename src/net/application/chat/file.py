"""Mensagem de transferência de arquivo do protocolo de chat."""

import base64
import json
from datetime import datetime
from typing import TypedDict

from net.application.chat.message_type import MessageType


class FilePayload(TypedDict):
    """Payload JSON de uma mensagem de arquivo."""

    type: str
    sender: str
    recipient: str
    timestamp: str
    name: str
    mime: str
    size: int
    data: str


class FileMessage:
    """Mensagem de transferência de arquivo."""

    type = MessageType.FILE

    def __init__(
        self,
        sender: str,
        recipient: str,
        name: str,
        mime: str,
        data: bytes,
        timestamp: datetime | None = None,
    ) -> None:
        """Inicializa a mensagem de arquivo.

        Args:
            sender (str): Nome do remetente.
            recipient (str): Nome do destinatário.
            name (str): Nome do arquivo.
            mime (str): Tipo MIME do arquivo.
            data (bytes): Conteúdo bruto do arquivo.
            timestamp (datetime | None): Momento do envio; usa agora se None.
        """
        self.sender = sender
        self.recipient = recipient
        self.name = name
        self.mime = mime
        self.data = data
        self.size = len(data)
        self.timestamp = timestamp or datetime.now()

    def encode(self) -> bytes:
        """Serializa a mensagem para bytes JSON (conteúdo em Base64).

        Returns:
            bytes: A mensagem serializada em JSON.
        """
        payload: FilePayload = {
            "type": MessageType.FILE,
            "sender": self.sender,
            "recipient": self.recipient,
            "timestamp": self.timestamp.isoformat(),
            "name": self.name,
            "mime": self.mime,
            "size": self.size,
            "data": base64.b64encode(self.data).decode(),
        }
        return json.dumps(payload).encode()

    @staticmethod
    def decode(raw: bytes) -> FileMessage:
        """Desserializa uma mensagem de arquivo a partir de bytes JSON.

        Args:
            raw (bytes): Bytes JSON da mensagem.

        Returns:
            FileMessage: A mensagem desserializada.

        Raises:
            ValueError: Se o payload não for do tipo `file`.
        """
        payload: FilePayload = json.loads(raw)
        if payload["type"] != MessageType.FILE:
            raise ValueError(f"Tipo inválido para FileMessage: {payload['type']!r}")

        return FileMessage(
            sender=payload["sender"],
            recipient=payload["recipient"],
            name=payload["name"],
            mime=payload["mime"],
            data=base64.b64decode(payload["data"]),
            timestamp=datetime.fromisoformat(payload["timestamp"]),
        )
