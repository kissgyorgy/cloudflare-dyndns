import ipaddress
from typing import Literal, Union

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
A = Literal["A"]
AAAA = Literal["AAAA"]
RecordType = Union[A, AAAA]


def get_record_type(ip: IPAddress) -> RecordType:
    return "A" if ip.version == 4 else "AAAA"


class ExitCode:
    OK = 0
    UNKNOWN_ERROR = 1
    IP_SERVICE_ERROR = 2
    CLOUDFLARE_ERROR = 3
