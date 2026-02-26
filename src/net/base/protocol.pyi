from socket import socket

PROBABILIDADE_PERDA: float
PROBABILIDADE_CORRUPCAO: float
LATENCIA_MIN: float
LATENCIA_MAX: float

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
    def to_dict(self) -> dict[str, object]: ...

class Pacote:
    src_vip: str
    dst_vip: str
    ttl: int
    data: dict[str, object]

    def __init__(
        self,
        src_vip: str,
        dst_vip: str,
        ttl: int,
        segmento_dict: dict[str, object],
    ) -> None: ...
    def to_dict(self) -> dict[str, object]: ...

class Quadro:
    src_mac: str
    dst_mac: str
    data: dict[str, object]
    fcs: int

    def __init__(
        self,
        src_mac: str,
        dst_mac: str,
        pacote_dict: dict[str, object],
    ) -> None: ...
    def serializar(self) -> bytes: ...
    @staticmethod
    def deserializar(
        bytes_recebidos: bytes,
    ) -> tuple[dict[str, object] | None, bool]: ...

def enviar_pela_rede_ruidosa(
    socket_udp: socket,
    bytes_dados: bytes,
    endereco_destino: tuple[str, int],
) -> None: ...
