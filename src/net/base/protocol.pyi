from socket import socket
from typing import TypedDict

PROBABILIDADE_PERDA: float
PROBABILIDADE_CORRUPCAO: float
LATENCIA_MIN: float
LATENCIA_MAX: float

class SegmentoDict(TypedDict):
    seq_num: int
    is_ack: bool
    payload: dict[str, object]

class PacoteDict(TypedDict):
    src_vip: str
    dst_vip: str
    ttl: int
    data: SegmentoDict

class QuadroDict(TypedDict):
    src_mac: str
    dst_mac: str
    data: PacoteDict
    fcs: int

class Segmento:
    seq_num: int
    is_ack: bool
    payload: dict[str, object]

    def __init__(
        self,
        seq_num: int,
        is_ack: bool,
        payload: dict[str, object],
    ) -> None: ...
    def to_dict(self) -> SegmentoDict: ...

class Pacote:
    src_vip: str
    dst_vip: str
    ttl: int
    data: SegmentoDict

    def __init__(
        self,
        src_vip: str,
        dst_vip: str,
        ttl: int,
        segmento_dict: SegmentoDict,
    ) -> None: ...
    def to_dict(self) -> PacoteDict: ...

class Quadro:
    src_mac: str
    dst_mac: str
    data: PacoteDict
    fcs: int

    def __init__(
        self,
        src_mac: str,
        dst_mac: str,
        pacote_dict: PacoteDict,
    ) -> None: ...
    def serializar(self) -> bytes: ...
    @staticmethod
    def deserializar(
        bytes_recebidos: bytes,
    ) -> tuple[QuadroDict | None, bool]: ...

def enviar_pela_rede_ruidosa(
    socket_udp: socket,
    bytes_dados: bytes,
    endereco_destino: tuple[str, int],
) -> None: ...
