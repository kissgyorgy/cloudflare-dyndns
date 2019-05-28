import sys
import json
import ipaddress
from pathlib import Path
import requests
import CloudFlare

CACHE_PATH = "change-ip.cache"
CLOUDFLARE_EMAIL = "admin@example.com"
CLOUDFLARE_API_KEY = "<api key from CloudFlare My Profile>"
DOMAINS_TO_UPDATE = []

GET_IP_SERVICES = [
    "https://ifconfig.co/ip",
    "https://checkip.amazonaws.com/",
    "https://ifconfig.me/ip",
    "https://dynamicdns.park-your-domain.com/getip",
]


def get_ip(service_urls):
    print("Checking current IP address...")
    for ip_service in service_urls:
        res = requests.get(ip_service)
        if res.ok:
            ip = ipaddress.IPv4Address(res.text.strip())
            print(f"Current IP address from {ip_service}: {ip}")
            return ip
    else:
        sys.exit("Couldn't determine current IP address.")


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
            return self._cache
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


class CloudFlareClient:
    def __init__(self, email, apikey):
        self._cf = CloudFlare.CloudFlare(email=email, token=apikey)

    def get_records(self, domain):
        filter_by_name = {"name": domain}
        try:
            zone_list = self._cf.zones.get(params=filter_by_name)
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            sys.exit(str(e))

        # not sure if multiple zones can exist for the same domain
        try:
            zone = zone_list[0]
        except KeyError:
            sys.exit(f'Cannot find domain "{domain}" at CloudFlare')

        try:
            dns_records = self._cf.zones.dns_records.get(
                zone["id"], params=filter_by_name
            )
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            sys.exit(str(e))

        for record in dns_records:
            if record["type"] == "A" and record["name"] == domain:
                break
        else:
            sys.exit(f"Cannot find A record for {domain}")

        return zone["id"], record["id"]

    def update_A_record(self, ip, domain, zone_id, record_id):
        print(f'Updating "{domain}" A record.')
        payload = {"name": "@", "type": "A", "content": str(ip)}
        try:
            self._cf.zones.dns_records.put(zone_id, record_id, data=payload)
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            sys.exit(str(e))


def main():
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


if __name__ == "__main__":
    main()
