"""Configuração de logging colorido para o terminal."""

import logging

# Códigos ANSI básicos
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\x1b[36m",  # ciano
    logging.INFO: "\x1b[32m",  # verde
    logging.WARNING: "\x1b[33m",  # amarelo
    logging.ERROR: "\x1b[31m",  # vermelho
    logging.CRITICAL: "\x1b[35m",  # magenta
}


class ColorFormatter(logging.Formatter):
    """Formatter que colore o nível e destaca o timestamp no terminal."""

    FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"
    FORMAT_NO_DATE = "%(levelname)-8s  %(message)s"

    def __init__(self, *, show_date: bool = True) -> None:
        """Inicializa o formatter.

        Args:
            show_date (bool): Se `True`, inclui timestamp na saída.
        """
        super().__init__()
        self._show_date = show_date

    def format(self, record: logging.LogRecord) -> str:
        """Formata o registro com cores ANSI.

        Args:
            record (logging.LogRecord): O registro de log.

        Returns:
            str: Linha formatada e colorida.
        """
        color = _LEVEL_COLORS.get(record.levelno, "")
        colored_level = f"{_BOLD}{color}{record.levelname:<8}{_RESET}"

        original_levelname = record.levelname
        record.levelname = colored_level

        if self._show_date:
            format = self.FORMAT
            self.datefmt = "%Y-%m-%d %H:%M:%S"
        else:
            format = self.FORMAT_NO_DATE

        formatter = logging.Formatter(format, datefmt=self.datefmt)
        result = formatter.format(record)

        # Colorir o timestamp
        if self._show_date:
            parts = result.split("  ", 1)
            if len(parts) == 2:
                result = f"{_DIM}{parts[0]}{_RESET}  {parts[1]}"

        record.levelname = original_levelname
        return result


def setup_logging(
    level: int = logging.DEBUG,
    *,
    show_date: bool = True,
) -> None:
    """Configura o logging raiz com saída colorida no terminal.

    Deve ser chamado uma única vez, no ponto de entrada da aplicação.

    Args:
        level (int): Nível mínimo de log (ex.: `logging.DEBUG`).
        show_date (bool): Se `True`, inclui timestamp na saída.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(show_date=show_date))
    logging.basicConfig(level=level, handlers=[handler])
