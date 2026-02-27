"""Fábrica da pilha de rede.

Utiliza Address para definir como alvo da camada física simulada e VirtualAddress para
a camada de transporte.
"""

from __future__ import annotations


import socket
from pathlib import Path

from net.model.address import (
    Address,
    IPAddress,
    MACAddress,
    Port,
    VirtualAddress,
    VirtualIPAddress,
)
from net.stack.link.impl import SimpleLink
from net.stack.network.impl import HostNetwork, RouterNetwork
from net.stack.physical.impl import UDPSimulated
from net.stack.transport.impl import ReliableTransport

# --- Client A(lice) ---
CLIENT_A_NAME = "Alice"
CLIENT_A_MAC = MACAddress("AA:AA:AA:AA:AA:AA")
CLIENT_A_IP = IPAddress("127.0.0.1")
CLIENT_A_VIP = VirtualIPAddress("HOST_A")
CLIENT_A_PORT = Port(10000)
CLIENT_A_ADDRESS = Address(CLIENT_A_IP, CLIENT_A_PORT)
CLIENT_A_VADDRESS = VirtualAddress(CLIENT_A_VIP, CLIENT_A_PORT)

# --- Client B(ob) ---
CLIENT_B_NAME = "Bob"
CLIENT_B_MAC = MACAddress("BB:BB:BB:BB:BB:BB")
CLIENT_B_IP = IPAddress("127.0.0.1")
CLIENT_B_VIP = VirtualIPAddress("HOST_B")
CLIENT_B_PORT = Port(10001)
CLIENT_B_ADDRESS = Address(CLIENT_B_IP, CLIENT_B_PORT)
CLIENT_B_VADDRESS = VirtualAddress(CLIENT_B_VIP, CLIENT_B_PORT)

# --- Servidor ---
SERVER_NAME = "Servidor"
SERVER_MAC = MACAddress("CC:CC:CC:CC:CC:CC")
SERVER_IP = IPAddress("127.0.0.1")
SERVER_VIP = VirtualIPAddress("HOST_S")
SERVER_PORT = Port(10002)
SERVER_ADDRESS = Address(SERVER_IP, SERVER_PORT)
SERVER_VADDRESS = VirtualAddress(SERVER_VIP, SERVER_PORT)

# --- Downloads ---
# Pasta raiz onde os arquivos recebidos são salvos. Subpastas por destinatário.
DOWNLOADS_DIR: Path = Path(__file__).parents[3] / "downloads"


def ensure_downloads_dir() -> None:
    """Cria DOWNLOADS_DIR e um .gitignore com '*' se ainda não existirem."""
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    gitignore = DOWNLOADS_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")


# --- Roteador ---
ROUTER_NAME = "Roteador"
ROUTER_MAC = MACAddress("DD:DD:DD:DD:DD:DD")
ROUTER_IP = IPAddress("127.0.0.1")
ROUTER_VIP = VirtualIPAddress("HOST_R")
ROUTER_PORT = Port(10003)
ROUTER_ADDRESS = Address(ROUTER_IP, ROUTER_PORT)
ROUTER_VADDRESS = VirtualAddress(ROUTER_VIP, ROUTER_PORT)

# --- Tabela de mapeamento MAC -> Address (IP + Port) para a camada física simulada ---
MAC_TABLE: dict[MACAddress, Address] = {
    CLIENT_A_MAC: CLIENT_A_ADDRESS,
    CLIENT_B_MAC: CLIENT_B_ADDRESS,
    SERVER_MAC: SERVER_ADDRESS,
    ROUTER_MAC: ROUTER_ADDRESS,
}

# --- Tabelas ARP (VIP -> MAC) para a camada de enlace ---
# Alice, Bob e Servidor só enxergam o Roteador como próximo salto.
_ARP_TABLE_HOSTS: dict[VirtualIPAddress, MACAddress] = {
    ROUTER_VIP: ROUTER_MAC,
}

# O Roteador enxerga todos os hosts diretamente.
_ARP_TABLE_ROUTER: dict[VirtualIPAddress, MACAddress] = {
    CLIENT_A_VIP: CLIENT_A_MAC,
    CLIENT_B_VIP: CLIENT_B_MAC,
    SERVER_VIP: SERVER_MAC,
}

# --- Tabelas de roteamento (VIP destino -> VIP próximo salto) para a camada de rede ---
# Hosts encaminham todo tráfego ao Roteador como único gateway.
_ROUTING_TABLE_HOSTS: dict[VirtualIPAddress, VirtualIPAddress] = {
    CLIENT_A_VIP: ROUTER_VIP,
    CLIENT_B_VIP: ROUTER_VIP,
    SERVER_VIP: ROUTER_VIP,
}

# O Roteador roteia diretamente para cada host.
_ROUTING_TABLE_ROUTER: dict[VirtualIPAddress, VirtualIPAddress] = {
    CLIENT_A_VIP: CLIENT_A_VIP,
    CLIENT_B_VIP: CLIENT_B_VIP,
    SERVER_VIP: SERVER_VIP,
}

_ROUTING_REGISTRY: dict[str, dict[VirtualIPAddress, VirtualIPAddress]] = {
    CLIENT_A_NAME: _ROUTING_TABLE_HOSTS,
    CLIENT_B_NAME: _ROUTING_TABLE_HOSTS,
    SERVER_NAME: _ROUTING_TABLE_HOSTS,
    ROUTER_NAME: _ROUTING_TABLE_ROUTER,
}


HOST_REGISTRY: dict[
    str, tuple[MACAddress, Address, VirtualAddress, dict[VirtualIPAddress, MACAddress]]
] = {
    CLIENT_A_NAME: (
        CLIENT_A_MAC,
        CLIENT_A_ADDRESS,
        CLIENT_A_VADDRESS,
        _ARP_TABLE_HOSTS,
    ),
    CLIENT_B_NAME: (
        CLIENT_B_MAC,
        CLIENT_B_ADDRESS,
        CLIENT_B_VADDRESS,
        _ARP_TABLE_HOSTS,
    ),
    SERVER_NAME: (SERVER_MAC, SERVER_ADDRESS, SERVER_VADDRESS, _ARP_TABLE_HOSTS),
    ROUTER_NAME: (ROUTER_MAC, ROUTER_ADDRESS, ROUTER_VADDRESS, _ARP_TABLE_ROUTER),
}


def _get_host(
    name: str,
) -> tuple[MACAddress, Address, VirtualAddress, dict[VirtualIPAddress, MACAddress]]:
    if name not in HOST_REGISTRY:
        available = list(HOST_REGISTRY)
        raise KeyError(f"Host desconhecido: {name!r}. Disponíveis: {available}")
    return HOST_REGISTRY[name]


def build_physical_layer(name: str) -> UDPSimulated:
    """Cria e vincula a camada física simulada para o host informado.

    Cria um socket UDP, faz bind no endereço físico do host e devolve
    a camada física pronta para uso.

    Args:
        name (str): Nome do host conforme definido neste módulo
            (ex.: `CLIENT_A_NAME`, `SERVER_NAME`).

    Returns:
        UDPSimulated: Camada física com socket já vinculado.

    Raises:
        KeyError: Se `name` não existir no registro de hosts.
    """
    _, address, _, _ = _get_host(name)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((str(address.ip), int(address.port)))
    sock.settimeout(0.5)
    return UDPSimulated(sock, MAC_TABLE)


def build_link_layer(name: str) -> SimpleLink:
    """Cria a camada de enlace completa para o host informado.

    Cria a camada física subjacente (com socket vinculado) e devolve
    um SimpleLink configurado com o MAC local e a tabela ARP
    correspondente ao host.

    Args:
        name (str): Nome do host conforme definido neste módulo
            (ex.: `CLIENT_A_NAME`, `ROUTER_NAME`).

    Returns:
        SimpleLink: Camada de enlace pronta para uso.

    Raises:
        KeyError: Se `name` não existir no registro de hosts.
    """
    mac, _, _, arp_table = _get_host(name)
    physical = build_physical_layer(name)
    return SimpleLink(physical, mac, arp_table)


def build_network_layer(name: str) -> HostNetwork | RouterNetwork:
    """Cria a camada de rede completa para o host informado.

    Devolve RouterNetwork para o roteador e HostNetwork
    para os demais hosts. Em ambos os casos a camada de enlace subjacente
    (e a física) é construída internamente.

    Args:
        name (str): Nome do host conforme definido neste módulo
            (ex.: `CLIENT_A_NAME`, `ROUTER_NAME`).

    Returns:
        HostNetwork | RouterNetwork: Camada de rede pronta para uso.

    Raises:
        KeyError: Se `name` não existir no registro de hosts.
    """
    _, _, vaddress, _ = _get_host(name)
    routing_table = _ROUTING_REGISTRY[name]
    link = build_link_layer(name)
    if name == ROUTER_NAME:
        return RouterNetwork(link, vaddress.vip, routing_table)
    return HostNetwork(link, vaddress.vip, routing_table)


def build_transport_layer(name: str) -> ReliableTransport:
    """Cria a camada de transporte completa para o host informado.

    Cria a camada de rede subjacente (enlace e física inclusos) e devolve
    um ReliableTransport com o loop de despacho já ativo.

    Args:
        name (str): Nome do host conforme definido neste módulo
            (ex.: `CLIENT_A_NAME`, `SERVER_NAME`).

    Returns:
        ReliableTransport: Camada de transporte pronta para uso.

    Raises:
        KeyError: Se `name` não existir no registro de hosts.
        ValueError: Se `name` for o roteador (roteadores não têm transporte).
    """
    if name == ROUTER_NAME:
        raise ValueError("O roteador não possui camada de transporte.")

    _, _, vaddress, _ = _get_host(name)
    network = build_network_layer(name)
    return ReliableTransport(network, vaddress)
