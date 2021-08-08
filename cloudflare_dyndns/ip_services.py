from cloudflare_dyndns.types import IPAddress
import os
import ipaddress
from typing import Callable, List
import attr
import certifi
from . import printer


# Workaround for certifi resource location doesn't work with PyOxidizer.
# See: https://github.com/psf/requests/blob/v2.23.0/requests/utils.py#L40
# and: https://github.com/indygreg/PyOxidizer/issues/237
certifi.where = lambda: os.environ.get(
    "REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt"
)
import requests


class IPServiceError(Exception):
    """Raised when there is a problem during determining the IP Address
    through the IP Services.
    """

    def __init__(self, msg: str):
        super().__init__(msg)


def parse_cloudflare_trace_ip(res: str) -> str:
    """Parses the IP address line from the cloudflare trace service response.
    Example response:
        fl=114f30
        h=1.1.1.1
        ip=188.6.90.5
        ts=1567700692.298
        visit_scheme=https
        uag=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36
        colo=VIE
        http=http/2
        loc=HU
        tls=TLSv1.3
        sni=off
        warp=off
    """
    for line in res.splitlines():
        if line.startswith("ip="):
            ip = line[len("ip=") :]
            return ip


def strip_whitespace(res: str) -> str:
    """Strip whitespaces from the IP service response."""
    return res.strip()


@attr.define
class IPService:
    name: str
    url: str
    response_parser: Callable = strip_whitespace


IPV4_SERVICES = [
    IPService(
        "CloudFlare trace", "https://1.1.1.1/cdn-cgi/trace", parse_cloudflare_trace_ip,
    ),
    IPService("AWS check ip", "https://checkip.amazonaws.com/",),
    IPService("major.io icanhazip", "http://ipv4.icanhazip.com/"),
    IPService("Namecheap DynamicDNS", "https://dynamicdns.park-your-domain.com/getip",),
]


IPV6_SERVICES = [
    # These are always return IPv6 addresses first, when the machine has IPv6
    IPService("ip.tyk.nu", "https://ip.tyk.nu/"),
    IPService("wgetip.com", "https://wgetip.com/"),
    IPService("major.io icanhazip", "http://ipv6.icanhazip.com/"),
]


def _get_ip(ip_services: List[IPService], version: str) -> IPAddress:
    for ip_service in ip_services:
        printer.info(
            f"Checking current IPv{version} address with service: {ip_service.name} ({ip_service.url})"
        )
        try:
            res = requests.get(ip_service.url)
        except requests.exceptions.RequestException:
            printer.info(f"Service {ip_service.url} unreachable, skipping.")
            continue

        if not res.ok:
            printer.info(f"Service returned error status: {res.status_code}, skipping.")
            continue

        ip_str = ip_service.response_parser(res.text)
        try:
            ip = ipaddress.ip_address(ip_str)
        except ipaddress.AddressValueError:
            printer.warning(f"Service returned invalid IP Address: {ip_str}, skipping.")
            continue

        printer.info(f"Current IP address: {ip}")
        return ip

    else:
        raise IPServiceError(
            "Tried all IP Services, but couldn't determine current IP address."
        )


def get_ipv4(services: List[IPService] = IPV4_SERVICES) -> ipaddress.IPv4Address:
    ipv4 = _get_ip(services, "4")

    if not isinstance(ipv4, ipaddress.IPv4Address):
        raise IPServiceError(
            "IP Service returned IPv6 address instead of IPv4.\n"
            "There is a bug with the IP Service.",
        )

    return ipv4


def get_ipv6(services: List[IPService] = IPV6_SERVICES) -> ipaddress.IPv6Address:
    ipv6 = _get_ip(services, "6")

    if not isinstance(ipv6, ipaddress.IPv6Address):
        raise IPServiceError(
            "IP Service returned IPv4 address instead of IPv6.\n"
            "You either don't have an IPv6 address, or there is a bug with the IP Service.",
        )

    return ipv6
