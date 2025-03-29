import ipaddress

import pytest

from cloudflare_dyndns import ip_services as ips


@pytest.mark.parametrize("service", ips.IPV4_SERVICES)
def test_get_ipv4(service):
    ip = ips.get_ipv4([service])
    assert isinstance(ip, ipaddress.IPv4Address)


@pytest.mark.ipv6
@pytest.mark.parametrize("service", ips.IPV6_SERVICES)
def test_get_ipv6(service):
    ip = ips.get_ipv6([service])
    assert isinstance(ip, ipaddress.IPv6Address)
