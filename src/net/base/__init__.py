"""Bloco de construção base, fornecido pelo professor.

Expõe as estruturas de dados e funções de utilidade para as camadas relevantes
e deve ser obrigatoriamente utilizado pelas partes do projeto para montar o stack de
protocolos.
"""

from .protocol import Pacote as Packet
from .protocol import PacoteDict as PacketDict
from .protocol import Quadro as Frame
from .protocol import QuadroDict as FrameDict
from .protocol import Segmento as Segment
from .protocol import SegmentoDict as SegmentDict
from .protocol import enviar_pela_rede_ruidosa as send_over_noisy_channel

__all__ = [
    "Frame",
    "FrameDict",
    "Packet",
    "PacketDict",
    "Segment",
    "SegmentDict",
    "send_over_noisy_channel",
]
