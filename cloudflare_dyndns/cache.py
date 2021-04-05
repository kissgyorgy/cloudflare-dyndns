from pathlib import Path
import ipaddress
from typing import Dict, List, Optional, Union
import click
from pydantic import BaseModel
from .types import Domain


class InvalidCache(Exception):
    """Raised when we can't read the cache.
    It's either corrupted, an older version or unreadable.
    """


class ZoneRecord(BaseModel):
    zone_id: str
    record_id: str


class IPv4Cache(BaseModel):
    address: ipaddress.IPv4Address
    zone_records: Dict[Domain, ZoneRecord]
    updated_domains: List[str]


class IPv6Cache(BaseModel):
    address: ipaddress.IPv6Address
    zone_records: Dict[Domain, ZoneRecord]
    updated_domains: List[str]


class Cache(BaseModel):
    ipv4: Optional[IPv4Cache] = None
    ipv6: Optional[IPv6Cache] = None


class CacheManager:
    def __init__(self, cache_path: Union[str, Path], *, debug: bool = False):
        self._path = Path(cache_path).expanduser()
        self._debug = debug

    def ensure_path(self):
        if self._debug:
            click.echo(f"Creating cache directory: {self._path}")
        self._path.parent.mkdir(exist_ok=True, parents=True)

    def load(self) -> Cache:
        click.echo(f"Loading cache from: {self._path}")
        try:
            cache_json = self._path.read_text()
            cache = Cache.parse_raw(cache_json)
        except FileNotFoundError:
            click.echo(f"Cache file not found: {self._path}")
            return Cache()
        except Exception:
            message = "Invalid cache file"
            if self._debug:
                message += ": {cache_json}"
            click.secho(message, fg="yellow")
            raise InvalidCache

        if self._debug:
            click.echo(f"Loaded cache: {cache}")
        return cache

    def save(self, cache: Cache):
        cache_json = cache.json()
        if self._debug:
            click.echo(f"Saving cache: {cache_json}")
        click.echo(f"Saving cache to: {self._path}")
        self._path.write_text(cache_json)

    def delete(self):
        click.secho(f"Deleting cache at: {self._path}", fg="yellow")
        self._path.unlink(missing_ok=True)
