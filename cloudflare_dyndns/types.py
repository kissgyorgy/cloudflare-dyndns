import ipaddress
from typing import Union


IPv4or6Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def get_record_type(ip: IPv4or6Address):
    return "A" if ip.version == 4 else "AAAA"
