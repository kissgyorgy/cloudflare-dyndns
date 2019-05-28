#!/usr/bin/env python3
import sys
import json
import ipaddress
from pathlib import Path
import requests
import CloudFlare

CACHE_PATH = "cfdns.cache"
CLOUDFLARE_EMAIL = "admin@example.com"
CLOUDFLARE_API_KEY = "<api key from CloudFlare My Profile>"
DOMAINS_TO_UPDATE = []

GET_IP_SERVICES = [
    "https://ifconfig.co/ip",
    "https://checkip.amazonaws.com/",
    "https://ifconfig.me/ip",
    "https://dynamicdns.park-your-domain.com/getip",
]


class IPServiceError(Exception):
    """Couldn't determine current IP address."""


def get_ip(service_urls):
    print("Checking current IP address...")
    for ip_service in service_urls:
        try:
            res = requests.get(ip_service)
        except requests.exceptions.RequestException:
            print(f"Service {ip_service} unreachable, skipping.")
            continue

        if res.ok:
            ip = ipaddress.IPv4Address(res.text.strip())
            print(f"Current IP address from {ip_service}: {ip}")
            return ip
    else:
        raise IPServiceError


class Cache:
    def __init__(self, cache_path: str):
        self._path = Path(cache_path)
        self._cache = {"ip": None, "zone_records": {}}

    def load(self):
        print(f"Loading cache from {self._path}")
        try:
            with self._path.open() as fp:
                self._cache = json.load(fp)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            print("Invalid cache file, deleting")
            self._path.unlink()

    def save(self):
        print("Saving cache")
        with self._path.open("w") as fp:
            json.dump(self._cache, fp)

    def get_ip(self):
        ip = self._cache.get("ip", None)
        return ipaddress.IPv4Address(ip) if ip else None

    def set_ip(self, ip: ipaddress.IPv4Address):
        self._cache["ip"] = str(ip)

    def get_ids(self, domain):
        records = self._cache["zone_records"][domain]
        return records["zone_id"], records["record_id"]

    def update_ids(self, domain, zone_id, record_id):
        self._cache["zone_records"][domain] = {
            "zone_id": zone_id,
            "record_id": record_id,
        }


class CloudFlareError(Exception):
    """We can't communicate with CloudFlare API as expected."""


class CloudFlareClient:
    def __init__(self, email, apikey):
        self._cf = CloudFlare.CloudFlare(email=email, token=apikey)

    def get_records(self, domain):
        filter_by_name = {"name": domain}
        zone_list = self._cf.zones.get(params=filter_by_name)

        # not sure if multiple zones can exist for the same domain
        try:
            zone = zone_list[0]
        except IndexError:
            raise CloudFlareError(f'Cannot find domain "{domain}" at CloudFlare')

        dns_records = self._cf.zones.dns_records.get(zone["id"], params=filter_by_name)

        for record in dns_records:
            if record["type"] == "A" and record["name"] == domain:
                break
        else:
            raise CloudFlareError(f"Cannot find A record for {domain}")

        return zone["id"], record["id"]

    def update_A_record(self, ip, domain, zone_id, record_id):
        print(f'Updating "{domain}" A record.')
        payload = {"name": "@", "type": "A", "content": str(ip)}
        self._cf.zones.dns_records.put(zone_id, record_id, data=payload)


def start_update():
    cache = Cache(CACHE_PATH)
    cache.load()
    cf = CloudFlareClient(CLOUDFLARE_EMAIL, CLOUDFLARE_API_KEY)

    current_ip = get_ip(GET_IP_SERVICES)

    if current_ip == cache.get_ip():
        print("IP address is unchanged")
        return
    else:
        cache.set_ip(current_ip)

    for domain in DOMAINS_TO_UPDATE:
        try:
            zone_id, record_id = cache.get_ids(domain)
        except KeyError:
            zone_id, record_id = cf.get_records(domain)
            cache.update_ids(domain, zone_id, record_id)

        cf.update_A_record(current_ip, domain, zone_id, record_id)

    cache.save()
    print("Done.")


def main():
    try:
        start_update()
    except IPServiceError:
        print(IPServiceError.__doc__)
        return 1
    except (CloudFlare.exceptions.CloudFlareAPIError, CloudFlareError) as e:
        print(e)
        return 2
    except Exception:
        return 3
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
