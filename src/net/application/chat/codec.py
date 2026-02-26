"""Dispatcher de desserialização do protocolo de chat."""

import json

from net.application.chat.file import FileMessage
from net.application.chat.message_type import MessageType
from net.application.chat.system import SystemMessage
from net.application.chat.text import TextMessage

type Message = TextMessage | FileMessage | SystemMessage


def decode(raw: bytes) -> Message:
    """Desserializa qualquer mensagem do protocolo a partir de bytes JSON.

    Lê apenas o campo `type` para escolher o decoder correto.

    Args:
        raw (bytes): Bytes JSON da mensagem.

    Returns:
        Message: A mensagem desserializada no tipo correto.

    Raises:
        ValueError: Se `type` for desconhecido.
    """
    message_type = json.loads(raw).get("type")
    match message_type:
        case MessageType.TEXT:
            return TextMessage.decode(raw)

        case MessageType.FILE:
            return FileMessage.decode(raw)

        case MessageType.SYSTEM:
            return SystemMessage.decode(raw)

        case _:
            raise ValueError(f"Tipo de mensagem desconhecido: {message_type!r}")
