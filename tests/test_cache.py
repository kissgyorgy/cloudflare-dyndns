import ipaddress
from cloudflare_dyndns.cache import (
    CacheManager,
    Cache,
    IPCache,
    InvalidCache,
    ZoneRecord,
)
import pytest


def test_roundtrip(tmp_path):
    manager = CacheManager(tmp_path / "cache.json")
    cache = Cache(
        ipv4=IPCache(
            address=ipaddress.IPv4Address("127.0.0.1"),
            updated_domains={"example.com": ZoneRecord(zone_id="1", record_id="2")},
        ),
        ipv6=IPCache(
            address=ipaddress.IPv6Address("2001:db8:85a3:8d3:1319:8a2e:370:7348"),
            updated_domains={"example.io": ZoneRecord(zone_id="3", record_id="4")},
        ),
    )
    manager.save(cache)
    cache_loaded = manager.load()

    assert id(cache) != id(cache_loaded)
    assert cache == cache_loaded


def test_missing_cache(capsys):
    manager = CacheManager("doesntexists")
    cache = manager.load()
    assert cache == Cache()
    assert "Cache file not found" in capsys.readouterr().out


def test_invalid_cache(tmp_path, capsys):
    cache_path = tmp_path / "invalid_cache.json"
    cache_path.write_text("Invalid cache")
    manager = CacheManager(cache_path)
    with pytest.raises(InvalidCache):
        manager.load()
    assert "Invalid cache file" in capsys.readouterr().out
