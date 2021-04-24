import ipaddress
from typing import Literal, Union, NewType


IPv4or6Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
A = Literal["A"]
AAAA = Literal["AAAA"]
RecordType = Union[A, AAAA]
Domain = NewType("Domain", str)


def get_record_type(ip: IPv4or6Address) -> RecordType:
    return "A" if ip.version == 4 else "AAAA"
