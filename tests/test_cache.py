import ipaddress

import pytest

from cloudflare_dyndns.cache import Cache, CacheManager, IPCache, ZoneRecord


@pytest.fixture
def cache():
    return Cache(
        ipv4=IPCache(
            address=ipaddress.IPv4Address("127.0.0.1"),
            updated_domains={"example.com": ZoneRecord(zone_id="1", record_id="2")},
        ),
        ipv6=IPCache(
            address=ipaddress.IPv6Address("2001:db8:85a3:8d3:1319:8a2e:370:7348"),
            updated_domains={"example.io": ZoneRecord(zone_id="3", record_id="4")},
        ),
    )


def test_roundtrip(tmp_path, cache):
    manager = CacheManager(tmp_path / "cache.json")
    manager.save(cache)
    old_cache, _ = manager.load()

    assert id(cache) != id(old_cache)
    assert cache == old_cache


def test_missing_cache(capsys):
    manager = CacheManager("doesntexists")
    old_cache, _ = manager.load()
    assert old_cache == Cache()
    assert "Cache file not found" in capsys.readouterr().out


def test_invalid_cache(tmp_path, capsys):
    cache_path = tmp_path / "invalid_cache.json"
    cache_path.write_text("Invalid cache")
    manager = CacheManager(cache_path)
    manager.load()
    assert "Invalid cache file" in capsys.readouterr().out
    assert not cache_path.exists()


def test_compare_caches(cache):
    cache1 = cache.model_copy(deep=True)
    cache2 = cache.model_copy(deep=True)
    assert (cache1 == cache2) is True

    cache2.ipv4.address = ipaddress.IPv4Address("127.0.0.2")
    assert (cache1 == cache2) is False


def test_default_caches_no_reference():
    cache1 = Cache()
    cache2 = Cache()
    cache1.ipv4.address = ipaddress.IPv4Address("127.0.0.1")
    assert cache1 != cache2
