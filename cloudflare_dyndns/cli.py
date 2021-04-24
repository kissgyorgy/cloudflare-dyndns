#!/usr/bin/env python3
import os
from typing import List, Optional, Union
from pathlib import Path
import click
import CloudFlare
from .cache import CacheManager, Cache, IPCache, InvalidCache, ZoneRecord
from .cloudflare import CloudFlareError, CloudFlareWrapper
from .types import IPv4or6Address, get_record_type
from .ip_services import IPServiceError, get_ipv4, get_ipv6


def get_domains(
    domains: List[str], force: bool, current_ip: IPv4or6Address, ip_cache: IPCache,
):
    if force:
        click.secho("Forced update, ignoring cache", fg="yellow")

    elif current_ip == ip_cache.address:
        updated_domains = ", ".join(ip_cache.updated_domains)
        if updated_domains:
            click.secho(
                f"Domains with this IP address in cache: {updated_domains}", fg="green",
            )
        else:
            click.echo("There are no domains with this IP address in cache.")
        missing_domains = set(domains) - set(ip_cache.updated_domains)
        if not missing_domains:
            click.secho(f"Every domain is up-to-date for {current_ip}.", fg="green")
            return None
        else:
            return missing_domains

    ip_cache.address = current_ip
    return domains


def update_domains(
    cf: CloudFlareWrapper,
    domains: List[str],
    ip_cache: IPCache,
    current_ip: IPv4or6Address,
):
    success = True
    for domain in domains:
        try:
            zone_record = ip_cache.updated_domains[domain]
            zone_id = zone_record.zone_id
            record_id = zone_record.record_id
        except KeyError:
            try:
                zone_id = cf.get_zone_id(domain)
                record_id = cf.get_record_id(domain, get_record_type(current_ip))
                zone_record = ZoneRecord(zone_id=zone_id, record_id=record_id)
            except Exception as e:
                click.secho(f'Failed to get domain records for "{domain}"', fg="red")
                click.secho(str(e), fg="red")
                success = False
                continue

        try:
            cf.update_record(domain, current_ip, zone_id, record_id)
        except Exception:
            click.secho(f'Failed to update domain "{domain}"', fg="red")
            success = False
            continue

        ip_cache.updated_domains[domain] = zone_record

    return success


# workaround for: https://github.com/pallets/click/issues/729
def parse_domains_args(domains: List[str], domains_env: Optional[str]):
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


def load_cache(cache_file: Path, force: bool):
    cache_manager = CacheManager(cache_file)
    cache_manager.ensure_path()

    if not force:
        try:
            return cache_manager, cache_manager.load()
        except InvalidCache:
            cache_manager.delete()

    return cache_manager, Cache()


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
    "-4/-no-4",
    "ipv4",
    help=("Turn on/off IPv4 detection and set A records.    [default: on]"),
    default=True,
)
@click.option(
    "-6/-no-6",
    "ipv6",
    help="Turn on/off IPv6 detection and set AAAA records. [default: off]",
    default=False,
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
def main(
    ctx: click.Context,
    domains: List[str],
    api_token: str,
    ipv4: bool,
    ipv6: bool,
    cache_file: str,
    force: bool,
    debug: bool,
):
    """A command line script to update CloudFlare DNS A and/or AAAA records
    based on the current IP address(es) of the machine running the script.

    For the main domain (the "@" record), simply put "example.com" \b
    Subdomains can also be specified, eg. "*.example.com" or "sub.example.com"

    You can set the list of domains to update in the CLOUDFLARE_DOMAINS
    environment variable, in which the domains has to be separated by
    whitespace, so don't forget to quote the value!

    The script supports both IPv4 and IPv6 addresses. The default is to set only
    A records for IPv4, which you can change with the relevant options.
    """
    if not ipv4 and not ipv6:
        raise click.UsageError(
            "You have to specify at least one IP mode; use -4 or -6.", ctx=ctx
        )

    domains_env = os.environ.get("CLOUDFLARE_DOMAINS")
    domains = parse_domains_args(domains, domains_env)

    cache_manager, cache = load_cache(Path(cache_file), force)
    cf = CloudFlareWrapper(api_token)

    exit_codes = set()
    ip_methods = [(get_ipv4, cache.ipv4)] if ipv4 else []
    ip_methods += [(get_ipv6, cache.ipv6)] if ipv6 else []

    for ip_func, ip_cache in ip_methods:
        exit_code = handle_update(ip_func, cf, domains, force, ip_cache, debug)
        exit_codes.add(exit_code)

    click.echo()
    cache_manager.save(cache)
    click.echo()

    exit_codes.remove(0)
    if not exit_codes:
        click.secho("Done.", fg="green")
        return

    # The smaller the exit code, the more specific the issue is
    final_exit_code = min(exit_codes)
    if final_exit_code != 0:
        click.secho("There were some errors during update.", fg="yellow")
        ctx.exit(final_exit_code)


def handle_update(get_ip_func, cf, domains, force, ip_cache, debug):
    click.echo()
    try:
        current_ip = get_ip_func()
    except IPServiceError as e:
        click.secho(str(e), fg="red")
        return 1

    try:
        domains_to_update = get_domains(domains, force, current_ip, ip_cache)
        if not domains_to_update:
            return 0
        success = update_domains(cf, domains_to_update, ip_cache, current_ip)

    except (CloudFlare.exceptions.CloudFlareAPIError, CloudFlareError) as e:
        click.secho(e, fg="red")
        if debug:
            raise
        return 2

    except Exception as e:
        click.secho(f"Unknown error: {e}", fg="red")
        if debug:
            raise
        return 3

    if not success:
        return 2

    return 0


if __name__ == "__main__":
    main()
