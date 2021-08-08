import ipaddress
from typing import Literal, Union, NewType


IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
A = Literal["A"]
AAAA = Literal["AAAA"]
RecordType = Union[A, AAAA]


def get_record_type(ip: IPAddress) -> RecordType:
    return "A" if ip.version == 4 else "AAAA"
