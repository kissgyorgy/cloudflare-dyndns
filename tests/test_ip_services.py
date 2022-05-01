import ipaddress
import pytest
from cloudflare_dyndns import ip_services as ips


def test_parse_cloudflare_trace_ipv4():
    trace_service_response = """fl=114f30
h=1.1.1.1
ip=199.12.81.4
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
    assert ips.parse_cloudflare_trace_ip(trace_service_response) == "199.12.81.4"


def test_parse_cloudflare_trace_ipv6():
    trace_service_response = """fl=75f49
h=[2606:4700:4700::1111]
ip=b322:31e3:f950:bad3:3589:8d9c:0812:c9c7
ts=1651050273.63
visit_scheme=https
uag=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36
colo=VIE
http=http/2
loc=HU
tls=TLSv1.3
sni=off
warp=off
gateway=off
"""
    assert ips.parse_cloudflare_trace_ip(trace_service_response) == "b322:31e3:f950:bad3:3589:8d9c:0812:c9c7"


@pytest.mark.parametrize("service", ips.IPV4_SERVICES)
def test_get_ipv4(service):
    ip = ips.get_ipv4([service])
    assert isinstance(ip, ipaddress.IPv4Address)


@pytest.mark.ipv6
@pytest.mark.parametrize("service", ips.IPV6_SERVICES)
def test_get_ipv6(service):
    ip = ips.get_ipv6([service])
    assert isinstance(ip, ipaddress.IPv6Address)
