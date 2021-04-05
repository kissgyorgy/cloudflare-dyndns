from pathlib import Path
import ipaddress
import pickle
import click


class RecordCache:
    def __init__(self, cache_path: str, debug: bool = False):
        self._path = Path(cache_path).expanduser()
        self._path.parent.mkdir(exist_ok=True, parents=True)
        self._cache = self._make_default()
        self._debug = debug

    def _make_default(self):
        return {"ip": None, "zone_records": {}, "updated_domains": set()}

    def load(self):
        click.echo(f"Loading cache from {self._path}")
        try:
            with self._path.open("rb") as fp:
                self._cache = pickle.load(fp)
                if self._debug:
                    click.echo(f"Loaded cache: {self._cache}")
        except FileNotFoundError:
            click.secho("Cache file not found")
            self._cache = self._make_default()
        except pickle.PickleError:
            raise InvalidCache

    def save(self):
        message = "Saving cache"
        if self._debug:
            message += f": {self._cache}"
        click.echo(message)
        with self._path.open("wb") as fp:
            pickle.dump(self._cache, fp)

    def delete(self):
        self._path.unlink(missing_ok=True)
        self._cache = self._make_default()

    def get_ip(self):
        return self._cache["ip"]

    def set_ip(self, ip: ipaddress.IPv4Address):
        self._cache["ip"] = ip
        self._cache["updated_domains"] = set()

    def get_ids(self, domain: str):
        records = self._cache["zone_records"][domain]
        return records["zone_id"], records["record_id"]

    def update_domain(self, domain: str, zone_id: str, record_id: str):
        self._cache["zone_records"][domain] = {
            "zone_id": zone_id,
            "record_id": record_id,
        }
        self._cache["updated_domains"].add(domain)

    def get_updated(self):
        return self._cache["updated_domains"]
