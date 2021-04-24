import functools
from typing import Optional
import click
import CloudFlare
from .types import IPv4or6Address, RecordType, get_record_type


class CloudFlareError(Exception):
    """We can't communicate with CloudFlare API as expected."""


class CloudFlareWrapper:
    def __init__(self, api_token):
        self._cf = CloudFlare.CloudFlare(token=api_token)

    @functools.lru_cache
    def get_zone_id(self, domain: str):
        without_subdomains = ".".join(domain.rsplit(".")[-2:])
        zone_list = self._cf.zones.get(params={"name": without_subdomains})

        # not sure if multiple zones can exist for the same domain
        try:
            zone = zone_list[0]
        except IndexError:
            raise CloudFlareError(f'Cannot find domain "{domain}" at CloudFlare')

        return zone["id"]

    @functools.lru_cache
    def _get_records(self, domain: str):
        zone_id = self.get_zone_id(domain)
        return self._cf.zones.dns_records.get(zone_id, params={"name": domain})

    @functools.lru_cache
    def get_record_id(self, domain: str, record_type: RecordType):
        for record in self._get_records(domain):
            if record["type"] == record_type and record["name"] == domain:
                return record["id"]

        raise CloudFlareError(f"Cannot find {record_type} record for {domain}")

    def update_record(
        self,
        domain: str,
        ip: IPv4or6Address,
        zone_id: Optional[str] = None,
        record_id: Optional[str] = None,
    ):
        zone_id = zone_id or self.get_zone_id(domain)
        record_type = get_record_type(ip)
        record_id = record_id or self.get_record_id(domain, record_type)
        click.echo(f'Updating "{domain}" {record_type} record.')
        payload = {"name": domain, "type": record_type, "content": str(ip)}
        self._cf.zones.dns_records.put(zone_id, record_id, data=payload)

    def set_record(self, domain: str, ip: IPv4or6Address):
        zone_id = self.get_zone_id(domain)
        record_type = get_record_type(ip)
        click.echo(f'Creating a new {record_type} record for "{domain}".')
        payload = {"name": domain, "type": record_type, "content": str(ip)}
        self._cf.zones.dns_records.post(zone_id, data=payload)
