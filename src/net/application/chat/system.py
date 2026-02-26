"""Mensagem de sistema do protocolo de chat."""

import json
from typing import TypedDict

from net.application.chat.message_type import MessageType


class SystemPayload(TypedDict):
    """Payload JSON de uma mensagem de sistema."""

    type: str
    content: str


class SystemMessage:
    """Notificação de sistema."""

    type = MessageType.SYSTEM

    def __init__(self, content: str) -> None:
        """Inicializa a mensagem de sistema.

        Args:
            content (str): Texto da notificação.
        """
        self.content = content

    def encode(self) -> bytes:
        """Serializa a mensagem para bytes JSON.

        Returns:
            bytes: A mensagem serializada em JSON.
        """
        payload: SystemPayload = {
            "type": MessageType.SYSTEM,
            "content": self.content,
        }
        return json.dumps(payload).encode()

    @staticmethod
    def decode(raw: bytes) -> SystemMessage:
        """Desserializa uma mensagem de sistema a partir de bytes JSON.

        Args:
            raw (bytes): Bytes JSON da mensagem.

        Returns:
            SystemMessage: A mensagem desserializada.

        Raises:
            ValueError: Se o payload não for do tipo ``system``.
        """
        payload: SystemPayload = json.loads(raw)
        if payload["type"] != MessageType.SYSTEM:
            raise ValueError(f"Tipo inválido para SystemMessage: {payload['type']!r}")

        return SystemMessage(content=payload["content"])
