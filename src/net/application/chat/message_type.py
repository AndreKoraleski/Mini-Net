"""Enumeração dos tipos de mensagem do protocolo de chat."""

from enum import StrEnum


class MessageType(StrEnum):
    """Tipos de mensagem suportados pelo protocolo."""

    TEXT = "text"
    FILE = "file"
    SYSTEM = "system"
