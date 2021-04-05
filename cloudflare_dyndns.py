#!/usr/bin/env python3
import functools
import os
import pickle
from typing import Callable, Optional
import ipaddress
from typing import Iterable
from pathlib import Path
import attr
import click
import certifi

# Workaround for certifi resource location doesn't work with PyOxidizer.
# See: https://github.com/psf/requests/blob/v2.23.0/requests/utils.py#L40
# and: https://github.com/indygreg/PyOxidizer/issues/237
certifi.where = lambda: os.environ.get(
    "REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt"
)

import requests
import CloudFlare


IPv4or6Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def parse_cloudflare_trace_ip(res: str):
    """Parses the IP address line from the cloudflare trace service response.
    Example response:
        fl=114f30
        h=1.1.1.1
        ip=188.6.90.5
        ts=1567700692.298
        visit_scheme=https
        uag=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36
        colo=VIE
        http=http/2
        loc=HU
        tls=TLSv1.3
        sni=off
        warp=off
    """
    for line in res.splitlines():
        if line.startswith("ip="):
            ip = line[len("ip=") :]
            return ip


def strip_whitespace(res):
    """Strip whitespaces from the IP service response."""
    return res.strip()


@attr.s(auto_attribs=True)
class IPService:
    name: str
    url: str
    response_parser: Callable = strip_whitespace


IPV4_SERVICES = [
    IPService(
        "CloudFlare trace", "https://1.1.1.1/cdn-cgi/trace", parse_cloudflare_trace_ip,
    ),
    IPService("AWS check ip", "https://checkip.amazonaws.com/",),
    IPService("Namecheap DynamicDNS", "https://dynamicdns.park-your-domain.com/getip",),
]


IPV6_SERVICES = [
    # These are always return IPv6 addresses first, when the machine has IPv6
    IPService("ip.tyk.nu", "https://ip.tyk.nu/"),
    IPService("wgetip.com", "https://wgetip.com/"),
    IPService("WhatIs MyIPAddress", "https://bot.whatismyipaddress.com"),
]


class IPServiceError(Exception):
    """Couldn't determine current IP address."""


def get_ip(ip_services):
    for ip_service in ip_services:
        click.echo(
            f"Checking current IP address with service: {ip_service.name} ({ip_service.url})"
        )
        try:
            res = requests.get(ip_service.url)
        except requests.exceptions.RequestException:
            click.echo(f"Service {ip_service.url} unreachable, skipping.")
            continue

        if not res.ok:
            continue

        ip_str = ip_service.response_parser(res.text)
        ip = ipaddress.IPv4Address(ip_str)
        click.echo(f"Current IP address: {ip}")
        return ip

    else:
        raise IPServiceError


class Cache:
    def __init__(self, cache_path: str, debug=False):
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
            click.secho("Invalid cache file, deleting", fg="yellow")
            self.delete()

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


def get_record_type(ip: IPv4or6Address):
    return "A" if ip.version == 4 else "AAAA"


class CloudFlareClient:
    def __init__(self, api_token):
        self._cf = CloudFlare.CloudFlare(token=api_token)

    @functools.lru_cache
    def get_zone_id(self, domain):
        without_subdomains = ".".join(domain.rsplit(".")[-2:])
        zone_list = self._cf.zones.get(params={"name": without_subdomains})

        # not sure if multiple zones can exist for the same domain
        try:
            zone = zone_list[0]
        except IndexError:
            raise CloudFlareError(f'Cannot find domain "{domain}" at CloudFlare')

        return zone["id"]

    @functools.lru_cache
    def _get_records(self, domain):
        zone_id = self.get_zone_id(domain)
        return self._cf.zones.dns_records.get(zone_id, params={"name": domain})

    @functools.lru_cache
    def get_record_id(self, domain: str, record_type: str):
        assert record_type in {"A", "AAAA"}

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


def get_domains(domains, force, current_ip, cache, debug=False):
    if force:
        click.secho("Forced update, deleting cache.", fg="yellow")
        cache.delete()
        cache.set_ip(current_ip)
        return domains

    elif current_ip == cache.get_ip():
        click.secho(
            f"Domains with this IP address in cache: {', '.join(cache.get_updated())}",
            fg="green",
        )
        missing_domains = set(domains) - cache.get_updated()
        if not missing_domains:
            click.secho("Every domain is up-to-date, quitting.", fg="green")
            return None
        else:
            return missing_domains

    else:
        cache.set_ip(current_ip)
        return domains


def update_domains(cf, domains, cache, current_ip):
    success = True
    for domain in domains:
        try:
            zone_id, record_id = cache.get_ids(domain)
        except KeyError:
            try:
                zone_id, record_id = cf.get_records(domain)
            except Exception:
                click.secho(f'Failed to get domain records for "{domain}"', fg="red")
                success = False
                continue

        try:
            cf.update_A_record(current_ip, domain, zone_id, record_id)
        except Exception:
            click.secho(f'Failed to update domain "{domain}"', fg="red")
            success = False
            continue
        else:
            cache.update_domain(domain, zone_id, record_id)

    return success


# workaround for: https://github.com/pallets/click/issues/729
def _parse_domains_args(domains: Iterable, domains_env: Optional[str]):
    if not domains and not domains_env:
        raise click.BadArgumentUsage(
            "You need to specify either domains argument or CLOUDFLARE_DOMAINS environment variable!"
        )
    elif domains and domains_env:
        raise click.BadArgumentUsage(
            "Ambiguous domain list, use either argument list or CLOUDFLARE_DOMAINS environment variable, not both!"
        )
    elif domains_env:
        # same method as in click.ParamType.split_envvar_value, which was the default before
        domains = (domains_env or "").split()

    click.echo("Domains to update: " + ", ".join(domains))
    return domains


@click.command()
@click.argument("domains", nargs=-1)
@click.option(
    "--api-token",
    required=True,
    envvar="CLOUDFLARE_API_TOKEN",
    help=(
        "CloudFlare API Token (You can create one at My Profile page / API Tokens tab). "
        "Can be set with CLOUDFLARE_API_TOKEN environment variable."
    ),
)
@click.option(
    "--cache-file",
    help="Cache file",
    type=click.Path(dir_okay=False, writable=True, readable=True),
    default="~/.cache/cloudflare-dynds/ip.cache",
    show_default=True,
)
@click.option("--force", is_flag=True, help="Delete cache and update every domain")
@click.option(
    "--debug", is_flag=True, help="More verbose messages and Exception tracebacks"
)
@click.pass_context
def main(ctx, domains, api_token, cache_file, force, debug):
    """A simple command line script to update CloudFlare DNS A records
    with the current IP address of the machine running the script.

    For the main domain (the "@" record), simply put "example.com" \b
    Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

    You can set the list of domains to update in the CLOUDFLARE_DOMAINS
    environment variable, in which the domains has to be separated by
    whitespace, so don't forget to quote the value!
    """
    domains_env = os.environ.get("CLOUDFLARE_DOMAINS")
    domains = _parse_domains_args(domains, domains_env)

    try:
        current_ip = get_ip(IP_SERVICES)
    except IPServiceError:
        click.secho(IPServiceError.__doc__, fg="red")
        ctx.exit(1)

    cache = Cache(cache_file, debug)
    cf = CloudFlareClient(api_token)

    try:
        if not force:
            cache.load()
        domains_to_update = get_domains(domains, force, current_ip, cache, debug)
        if not domains_to_update:
            return
        success = update_domains(cf, domains_to_update, cache, current_ip)
        cache.save()
    except (CloudFlare.exceptions.CloudFlareAPIError, CloudFlareError) as e:
        click.secho(e, fg="red")
        if debug:
            raise
        ctx.exit(2)
    except Exception as e:
        click.secho(f"Unknown error: {e}", fg="red")
        if debug:
            raise
        ctx.exit(3)

    if not success:
        click.secho("There were some errors during update.", fg="yellow")
        ctx.exit(2)

    click.secho("Done.", fg="green")


if __name__ == "__main__":
    main()
