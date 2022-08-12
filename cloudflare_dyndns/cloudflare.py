import functools
import ssl
from typing import Optional

import httpx

from . import printer
from .cache import ssl_context
from .types import IPAddress, RecordType, get_record_type


class CloudFlareError(Exception):
    """We can't communicate with CloudFlare API as expected."""


class CloudFlareWrapper:
    API_URL = "https://api.cloudflare.com/client/v4/"

    def __init__(self, api_token: str):
        headers = {"Authorization": f"Bearer {api_token}"}
        self._client = httpx.Client(base_url=self.API_URL, headers=headers, verify=ssl_context)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        res = self._client.request(method, url, **kwargs)
        result = res.json()["result"]
        return result

    @functools.lru_cache
    def get_zone_id(self, domain: str) -> str:
        without_subdomains = ".".join(domain.rsplit(".")[-2:])
        zone_list = self._request("GET", "/zones", params={"name": without_subdomains})

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
        try:
            return self._request("GET", f"/zones/{zone_id}/dns_records", params={"name": domain})
        except httpx.RequestError as e:
            raise CloudFlareError(e.args)

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
            record = self._request("POST", f"/zones/{zone_id}/dns_records", json=payload)
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
            self._request("PUT", f"zones/{zone_id}/dns_records/{record_id}", json=payload)
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
        self._request("DELETE", f"zones/{zone_id}/dns_records/{record_id}")
