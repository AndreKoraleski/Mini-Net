"""Mensagem de texto do protocolo de chat."""

import json
from datetime import datetime
from typing import TypedDict

from net.application.chat.message_type import MessageType


class TextPayload(TypedDict):
    """Payload JSON de uma mensagem de texto."""

    type: str
    sender: str
    recipient: str
    content: str
    timestamp: str


class TextMessage:
    """Mensagem de texto entre dois usuários."""

    type = MessageType.TEXT

    def __init__(
        self,
        sender: str,
        recipient: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> None:
        """Inicializa a mensagem de texto.

        Args:
            sender (str): Nome do remetente.
            recipient (str): Nome do destinatário.
            content (str): Conteúdo da mensagem.
            timestamp (datetime | None): Momento do envio; usa agora se None.
        """
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.timestamp = timestamp or datetime.now()

    def encode(self) -> bytes:
        """Serializa a mensagem para bytes JSON.

        Returns:
            bytes: A mensagem serializada em JSON.
        """
        payload: TextPayload = {
            "type": MessageType.TEXT,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        return json.dumps(payload).encode()

    @staticmethod
    def decode(raw: bytes) -> TextMessage:
        """Desserializa uma mensagem de texto a partir de bytes JSON.

        Args:
            raw (bytes): Bytes JSON da mensagem.

        Returns:
            TextMessage: A mensagem desserializada.

        Raises:
            ValueError: Se o payload não for do tipo `text`.
        """
        payload: TextPayload = json.loads(raw)
        if payload["type"] != MessageType.TEXT:
            raise ValueError(f"Tipo inválido para TextMessage: {payload['type']!r}")

        return TextMessage(
            sender=payload["sender"],
            recipient=payload["recipient"],
            content=payload["content"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
        )
