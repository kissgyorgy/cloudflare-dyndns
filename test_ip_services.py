import pytest
import requests
import cloudflare_dyndns as cfdns


def test_parse_cloudflare_trace_ip():
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
    assert cfdns.parse_cloudflare_trace_ip(trace_service_response) == "199.12.81.4"


@pytest.mark.parametrize("service_url", (s.url for s in cfdns.IP_SERVICES))
def test_services_available(service_url):
    """This test hits all the services to check if they still work.
    It is an integration test.
    """
    res = requests.get(service_url)
    assert res.ok is True
