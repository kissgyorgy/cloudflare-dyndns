import functools
from typing import Optional
import CloudFlare
from .types import IPAddress, RecordType, get_record_type
from . import printer


class CloudFlareError(Exception):
    """We can't communicate with CloudFlare API as expected."""


class CloudFlareWrapper:
    def __init__(self, api_token: str):
        self._cf = CloudFlare.CloudFlare(token=api_token)

    @functools.lru_cache
    def get_zone_id(self, domain: str) -> str:
        without_subdomains = ".".join(domain.rsplit(".")[-2:])
        zone_list = self._cf.zones.get(params={"name": without_subdomains})

        # not sure if multiple zones can exist for the same domain
        try:
            zone = zone_list[0]
        except IndexError:
            printer.error(f'Cannot find domain "{domain}" at CloudFlare')
            raise CloudFlareError

        return zone["id"]

    @functools.lru_cache
    def _get_records(self, domain: str) -> dict:
        zone_id = self.get_zone_id(domain)
        return self._cf.zones.dns_records.get(zone_id, params={"name": domain})

    @functools.lru_cache
    def get_record_id(self, domain: str, record_type: RecordType) -> str:
        for record in self._get_records(domain):
            if record["type"] == record_type and record["name"] == domain:
                return record["id"]

        # This is not a fatal error yet
        printer.info(f'Failed to get domain records for "{domain}"')
        raise CloudFlareError(f"Cannot find {record_type} record for {domain}")

    def create_record(self, domain: str, ip: IPAddress, proxied: bool = False) -> str:
        zone_id = self.get_zone_id(domain)
        record_type = get_record_type(ip)
        printer.info(f'Creating a new {record_type} record for "{domain}".')
        payload = {
            "name": domain,
            "type": record_type,
            "content": str(ip),
            "ttl": 1,
            "proxied": proxied,
        }
        try:
            record = self._cf.zones.dns_records.post(zone_id, data=payload)
        except Exception as e:
            printer.error(f'Failed to create new record for "{domain}": {e}')
            raise
        return record["id"]

    def update_record(
        self,
        domain: str,
        ip: IPAddress,
        zone_id: Optional[str] = None,
        record_id: Optional[str] = None,
        proxied: bool = False,
    ):
        zone_id = zone_id or self.get_zone_id(domain)
        record_type = get_record_type(ip)
        record_id = record_id or self.get_record_id(domain, record_type)
        printer.info(f'Updating "{domain}" {record_type} record.')
        payload = {
            "name": domain,
            "type": record_type,
            "content": str(ip),
            "proxied": proxied,
        }
        try:
            self._cf.zones.dns_records.put(zone_id, record_id, data=payload)
        except Exception as e:
            printer.error(f'Failed to update domain "{domain}": {e}')
            raise

    def delete_record(self, domain: str, record_type: RecordType):
        printer.warning(f'Deleting {record_type} record for "{domain}".')
        zone_id = self.get_zone_id(domain)
        try:
            record_id = self.get_record_id(domain, record_type)
        except CloudFlareError:
            printer.info(f'{record_type} record for "{domain}" doesn\'t exist.')
            return
        self._cf.zones.dns_records.delete(zone_id, record_id)
