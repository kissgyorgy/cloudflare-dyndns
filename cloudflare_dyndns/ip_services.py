import os
import ipaddress
from typing import Callable, List
import attr
import click
import certifi

# Workaround for certifi resource location doesn't work with PyOxidizer.
# See: https://github.com/psf/requests/blob/v2.23.0/requests/utils.py#L40
# and: https://github.com/indygreg/PyOxidizer/issues/237
certifi.where = lambda: os.environ.get(
    "REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt"
)
import requests


class IPServiceError(Exception):
    """Couldn't determine current IP address."""


def parse_cloudflare_trace_ip(res: str):
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


def strip_whitespace(res: str):
    """Strip whitespaces from the IP service response."""
    return res.strip()


@attr.s(auto_attribs=True)
class IPService:
    name: str
    url: str
    response_parser: Callable = strip_whitespace


IPV4_SERVICES = [
    IPService(
        "CloudFlare trace", "https://1.1.1.1/cdn-cgi/trace", parse_cloudflare_trace_ip,
    ),
    IPService("AWS check ip", "https://checkip.amazonaws.com/",),
    IPService("Namecheap DynamicDNS", "https://dynamicdns.park-your-domain.com/getip",),
]


IPV6_SERVICES = [
    # These are always return IPv6 addresses first, when the machine has IPv6
    IPService("ip.tyk.nu", "https://ip.tyk.nu/"),
    IPService("wgetip.com", "https://wgetip.com/"),
    IPService("WhatIs MyIPAddress", "https://bot.whatismyipaddress.com"),
]


def get_ip(ip_services: List[IPService]):
    for ip_service in ip_services:
        click.echo(
            f"Checking current IP address with service: {ip_service.name} ({ip_service.url})"
        )
        try:
            res = requests.get(ip_service.url)
        except requests.exceptions.RequestException:
            click.echo(f"Service {ip_service.url} unreachable, skipping.")
            continue

        if not res.ok:
            continue

        ip_str = ip_service.response_parser(res.text)
        ip = ipaddress.IPv4Address(ip_str)
        click.echo(f"Current IP address: {ip}")
        return ip

    else:
        raise IPServiceError
