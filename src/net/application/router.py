"""Módulo do roteador de rede."""

import logging

from net.stack.factory import ROUTER_NAME, build_network_layer
from net.stack.network.impl.router import RouterNetwork

logger = logging.getLogger(__name__)


class Router:
    """Roteador de rede."""

    def __init__(self, name: str = ROUTER_NAME) -> None:
        """Inicializa o roteador.

        Args:
            name (str): Nome do roteador conforme definido na fábrica.
        """
        self.network = build_network_layer(name)
        logger.info(
            "[ROTEADOR] Iniciado como %s (vip=%s).", name, self.network.local_vip
        )

    def run(self) -> None:
        """Processa pacotes indefinidamente, encaminhando via camada de rede."""
        logger.info("[ROTEADOR] Aguardando pacotes...")
        try:
            while True:
                self.network.receive()

        except KeyboardInterrupt:
            pass

        finally:
            self._log_stats()

    def _log_stats(self) -> None:
        """Registra as estatísticas de operação ao encerrar."""
        if not isinstance(self.network, RouterNetwork):
            return
        stats = self.network.stats
        logger.info(
            "[ROTEADOR] Encerrado.\n"
            "  Total processado : %d\n"
            "  Encaminhados      : %d\n"
            "  Descartados (TTL) : %d\n"
            "  Descartados (rota): %d",
            stats.total,
            stats.forwarded,
            stats.dropped_ttl,
            stats.dropped_unknown,
        )


def main() -> None:
    """Ponto de entrada para execução do roteador."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    Router().run()
