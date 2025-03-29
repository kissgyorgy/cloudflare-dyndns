import ssl
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import truststore
from pydantic import BaseModel

from . import printer
from .types import IPAddress

ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class InvalidCache(Exception):
    """Raised when we can't read the cache.
    It's either corrupted, an older version or unreadable.
    """


class ZoneRecord(BaseModel):
    zone_id: str
    record_id: str
    proxied: bool = False


class IPCache(BaseModel):
    address: Optional[IPAddress] = None
    updated_domains: Dict[str, ZoneRecord] = dict()

    def clear(self):
        self.address = None
        self.updated_domains = dict()


class Cache(BaseModel):
    ipv4: IPCache = IPCache()
    ipv6: IPCache = IPCache()

    def is_empty(self):
        return self == self.__class__()


class CacheManager:
    def __init__(
        self, cache_path: Union[str, Path], force: bool = False, *, debug: bool = False
    ):
        self._path = Path(cache_path).expanduser()
        self._force = force
        self._debug = debug

    def ensure_path(self):
        if self._debug:
            printer.info(f"Creating cache directory: {self._path}")
        if not self._path.parent.exists():
            self._path.parent.mkdir(parents=True)

    def load(self) -> Tuple[Cache, Cache]:
        new_cache = Cache()

        if self._force:
            printer.warning("Forced update, ignoring cache")
            return Cache(), new_cache

        try:
            return self._load(), new_cache
        except InvalidCache:
            self.delete()
            return Cache(), new_cache

    def _load(self):
        printer.info(f"Loading cache from: {self._path}")
        try:
            cache_json = self._path.read_text()
            cache = Cache.model_validate_json(cache_json)
        except FileNotFoundError:
            printer.info("Cache file not found.")
            return Cache()
        except Exception:
            message = "Invalid cache file"
            if self._debug:
                message += ": {cache_json}"
            printer.warning(message)
            raise InvalidCache

        if self._debug:
            printer.info(f"Loaded cache: {cache}")
        return cache

    def save(self, cache: Cache):
        cache_json = cache.model_dump_json(indent=2)
        if self._debug:
            printer.info(f"Saving cache: {cache_json}")
        printer.info(f"Saving cache to: {self._path}")
        self.ensure_path()
        self._path.write_text(cache_json)

    def delete(self):
        printer.warning(f"Deleting cache at: {self._path}")
        self._path.unlink(missing_ok=True)
