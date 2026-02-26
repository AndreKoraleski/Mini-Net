"""Módulo para representar endereços IP, MAC e de Portas."""

from re import compile
from typing import Self


class IPAddress(str):
    """Representa um Endereço IP como uma string."""

    def __new__(cls, value: str) -> Self:
        """Valida o formato do IP e cria a instância.

        Args:
            value (str): O endereço IP a ser validado.

        Returns:
            Self: Uma instância de IPAddress se o formato for válido.

        Raises:
            ValueError: Se o formato do IP for inválido.
        """
        if not cls._is_valid_ip(value):
            raise ValueError(f"Endereço IP inválido: {value}")

        return str.__new__(cls, value)

    @staticmethod
    def _is_valid_ip(value: str) -> bool:
        parts = value.split(".")

        if len(parts) != 4:
            return False

        for part in parts:
            if not part.isdigit():
                return False

            if not 0 <= int(part) <= 255:
                return False

            if len(part) > 1 and part.startswith("0"):
                return False

        return True


class VIPAddress(str):
    """Representa um Endereço VIP sem validação específica."""

    def __new__(cls, value: str) -> Self:
        """Cria a instância de VIPAddress sem validação específica.

        Args:
            value (str): O endereço VIP a ser representado.

        Returns:
            Self: Uma instância de VIPAddress.
        """
        return str.__new__(cls, value)


_MAC_PATTERN = compile(r"^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$")


class MACAddress(str):
    """Representa um Endereço MAC como uma string."""

    def __new__(cls, value: str) -> Self:
        """Valida o formato do MAC e cria a instância.

        Args:
            value (str): O endereço MAC a ser validado.

        Returns:
            Self: Uma instância de MACAddress se o formato for válido.

        Raises:
            ValueError: Se o formato do MAC for inválido.
        """
        value = value.upper().replace("-", ":")
        if not _MAC_PATTERN.match(value):
            raise ValueError(f"Endereço MAC inválido: {value}")

        return str.__new__(cls, value)


class Port(int):
    """Representa um número de Porta como um inteiro."""

    def __new__(cls, value: int) -> Self:
        """Valida o número da porta e cria a instância.

        Args:
            value (int): O número da porta a ser validado.

        Returns:
            Self: Uma instância de Port se o número for válido.

        Raises:
            ValueError: Se o número da porta for inválido.
        """
        if not (0 <= value <= 65535):
            raise ValueError(f"Número de porta inválido: {value}")

        return int.__new__(cls, value)


class Address(tuple[IPAddress, Port]):
    """Representa um endereço de rede composto por um IP e uma Porta."""

    def __new__(cls, ip: str, port: int) -> Self:
        """Valida o IP e a Porta e cria a instância.

        Args:
            ip (str): O endereço IP a ser validado.
            port (int): O número da porta a ser validado.

        Returns:
            Self: Uma instância de Address se o IP e a Porta forem válidos.

        Raises:
            ValueError: Se o IP ou a Porta forem inválidos.
        """
        return super().__new__(cls, (IPAddress(ip), Port(port)))

    @property
    def ip(self) -> IPAddress:
        """Retorna o endereço IP do Address."""
        return self[0]

    @property
    def port(self) -> Port:
        """Retorna o número da porta do Address."""
        return self[1]


class VAdress(tuple[VIPAddress, Port]):
    """Representa um endereço VIP composto por um VIP e uma Porta."""

    def __new__(cls, vip: str, port: int) -> Self:
        """Valida o VIP e a Porta e cria a instância.

        Args:
            vip (str): O endereço VIP a ser validado.
            port (int): O número da porta a ser validado.

        Returns:
            Self: Uma instância de VAdress se o VIP e a Porta forem válidos.

        Raises:
            ValueError: Se o VIP ou a Porta forem inválidos.
        """
        return super().__new__(cls, (VIPAddress(vip), Port(port)))

    @property
    def vip(self) -> VIPAddress:
        """Retorna o endereço VIP do VAdress."""
        return self[0]

    @property
    def port(self) -> Port:
        """Retorna o número da porta do VAdress."""
        return self[1]
