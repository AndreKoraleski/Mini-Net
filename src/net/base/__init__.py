"""Bloco de construção base, fornecido pelo professor.

Expõe as estruturas de dados e funções de utilidade para as camadas relevantes
e deve ser obrigatoriamente utilizado pelas partes do projeto para montar o stack de
protocolos.
"""

from .protocol import Pacote as Packet
from .protocol import Quadro as Frame
from .protocol import Segmento as Segment
from .protocol import enviar_pela_rede_ruidosa as send_over_noisy_channel

__all__ = [
    "Frame",
    "Packet",
    "Segment",
    "send_over_noisy_channel",
]
