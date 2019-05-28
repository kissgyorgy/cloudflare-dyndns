#!/usr/bin/env python3
import pickle
import ipaddress
from pathlib import Path
import click
import requests
import CloudFlare

GET_IP_SERVICES = [
    "https://ifconfig.co/ip",
    "https://checkip.amazonaws.com/",
    "https://ifconfig.me/ip",
    "https://dynamicdns.park-your-domain.com/getip",
]


class IPServiceError(Exception):
    """Couldn't determine current IP address."""


def get_ip(service_urls):
    for ip_service in service_urls:
        click.echo(f"Checking current IP address with service: {ip_service}")
        try:
            res = requests.get(ip_service)
        except requests.exceptions.RequestException:
            click.echo(f"Service {ip_service} unreachable, skipping.")
            continue

        if res.ok:
            ip = ipaddress.IPv4Address(res.text.strip())
            click.echo(f"Current IP address: {ip}")
            return ip
    else:
        raise IPServiceError


class Cache:
    def __init__(self, cache_path: str):
        self._path = Path(cache_path)
        self._cache = {"ip": None, "zone_records": {}, "updated_domains": set()}

    def load(self):
        click.echo(f"Loading cache from {self._path}")
        try:
            with self._path.open("rb") as fp:
                self._cache = pickle.load(fp)
        except FileNotFoundError:
            pass
        except pickle.PickleError:
            click.secho("Invalid cache file, deleting", fg="yellow")
            self._path.unlink()

    def save(self):
        click.echo("Saving cache")
        with self._path.open("wb") as fp:
            pickle.dump(self._cache, fp)

    def get_ip(self):
        return self._cache["ip"]

    def set_ip(self, ip: ipaddress.IPv4Address):
        self._cache["ip"] = ip
        self._cache["updated_domains"] = set()

    def get_ids(self, domain):
        records = self._cache["zone_records"][domain]
        return records["zone_id"], records["record_id"]

    def update_domain(self, domain, zone_id, record_id):
        self._cache["zone_records"][domain] = {
            "zone_id": zone_id,
            "record_id": record_id,
        }
        self._cache["updated_domains"].add(domain)

    def get_updated(self):
        return self._cache["updated_domains"]


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
        click.echo(f'Updating "{domain}" A record.')
        payload = {"name": "@", "type": "A", "content": str(ip)}
        self._cf.zones.dns_records.put(zone_id, record_id, data=payload)


def start_update(domains, email, api_key, cache_file):
    success = True
    cache = Cache(cache_file)
    cache.load()
    cf = CloudFlareClient(email, api_key)

    current_ip = get_ip(GET_IP_SERVICES)
    click.secho(
        f"Domains with this IP address: {', '.join(cache.get_updated())}", fg="green"
    )
    missing_domains = set(domains) - cache.get_updated()

    if current_ip == cache.get_ip() and not missing_domains:
        click.secho("Every domain is up-to-date, quitting.", fg="green")
        return success
    else:
        cache.set_ip(current_ip)

    click.echo(f"Updating A records for domains: {', '.join(missing_domains)}...")
    for domain in missing_domains:
        try:
            zone_id, record_id = cache.get_ids(domain)
        except KeyError:
            try:
                zone_id, record_id = cf.get_records(domain)
            except Exception:
                click.secho(f'Failed to get domain records for "{domain}"', fg="red")
                success = False
                continue
            cache.update_domain(domain, zone_id, record_id)

        try:
            cf.update_A_record(current_ip, domain, zone_id, record_id)
        except Exception:
            click.secho(f'Failed to update domain "{domain}"', fg="red")
            success = False
            continue

    cache.save()
    click.secho("Done.", fg="green")
    return success


@click.command()
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--email",
    envvar="CLOUDFLARE_EMAIL",
    required=True,
    help=(
        "CloudFlare account email. "
        "Can be set with CLOUDFLARE_EMAIL environment variable"
    ),
)
@click.option(
    "--api-key",
    required=True,
    envvar="CLOUDFLARE_API_KEY",
    help=(
        "CloudFlare API key (You can find it at My Profile page). "
        "Can be set with CLOUDFLARE_API_KEY environment variable."
    ),
)
@click.option(
    "--cache-file",
    help="Cache file",
    type=click.Path(dir_okay=False, writable=True, readable=True),
    default="cfdns.cache",
    show_default=True,
)
@click.pass_context
def main(ctx, domains, email, api_key, cache_file):
    """A simple command line script to update CloudFlare DNS A records
    with the current IP address of the machine running the script.
    """
    try:
        success = start_update(domains, email, api_key, cache_file)
    except IPServiceError:
        click.secho(IPServiceError.__doc__, fg="red")
        ctx.exit(1)
    except (CloudFlare.exceptions.CloudFlareAPIError, CloudFlareError) as e:
        click.secho(e, fg="red")
        ctx.exit(2)
    except Exception as e:
        click.secho(f"Unknown error: {e}", fg="red")
        ctx.exit(3)

    if not success:
        click.secho("There were some errors during update.", fg="yellow")
        ctx.exit(2)


if __name__ == "__main__":
    main()
