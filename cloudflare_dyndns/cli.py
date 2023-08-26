#!/usr/bin/env python3
import os
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import click

from . import printer
from .cache import Cache, CacheManager, IPCache, ZoneRecord
from .cloudflare import CloudFlareError, CloudFlareWrapper
from .ip_services import IPServiceError, get_ipv4, get_ipv6
from .types import IPAddress, RecordType, get_record_type

cache_path = os.environ.get("XDG_CACHE_HOME", "~/.cache")
XDG_CACHE_HOME = Path(cache_path).expanduser()


def get_domains(
    domains: List[str],
    force: bool,
    current_ip: IPAddress,
    old_cache: IPCache,
    proxied: bool,
) -> Iterable[str]:
    if force:
        printer.warning("Forced update, ignoring cache")

    elif current_ip != old_cache.address:
        return domains

    updated_domains = {
        d
        for d, zone_record in old_cache.updated_domains.items()
        if zone_record.proxied is proxied
    }

    updated_domains_list = ", ".join(updated_domains)
    if updated_domains:
        printer.success(
            f"Domains with this IP address in cache: {updated_domains_list}"
        )
    else:
        printer.info("There are no domains with this IP address in cache.")

    missing_domains = set(domains) - updated_domains
    if not missing_domains:
        printer.success(f"Every domain is up-to-date for {current_ip}.")
        return []
    else:
        return missing_domains


def update_domains(
    cf: CloudFlareWrapper,
    domains: Iterable[str],
    old_cache: IPCache,
    new_cache: IPCache,
    current_ip: IPAddress,
    proxied: bool,
):
    success = True

    for domain in domains:
        update_record_failed = False

        cache_record = old_cache.updated_domains.get(domain)

        if cache_record is not None:
            zone_id = cache_record.zone_id
            record_id = cache_record.record_id
            try:
                cf.update_record(domain, current_ip, zone_id, record_id, proxied)
            except CloudFlareError:
                printer.error(f"Couldn't update record: {domain}")
                update_record_failed = True

        if cache_record is None or update_record_failed:
            try:
                zone_id = cf.get_zone_id(domain)
            except CloudFlareError:
                # TODO: try to create zone?
                success = False
                continue

            try:
                record_id = cf.get_record_id(domain, get_record_type(current_ip))
            except CloudFlareError:
                try:
                    record_id = cf.create_record(domain, current_ip, proxied)
                except CloudFlareError:
                    success = False
                    continue
            else:
                try:
                    cf.update_record(domain, current_ip, zone_id, record_id, proxied)
                except CloudFlareError:
                    success = False
                    continue

        zone_record = ZoneRecord(zone_id=zone_id, record_id=record_id, proxied=proxied)
        new_cache.updated_domains[domain] = zone_record

    return success


# workaround for: https://github.com/pallets/click/issues/729
def parse_domains_args(domains: List[str], domains_env: Optional[str]) -> List[str]:
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

    printer.info("Domains to update: " + ", ".join(domains))
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
    "--proxied",
    is_flag=True,
    help=(
        "Whether the records are receiving the performance "
        "and security benefits of Cloudflare."
    ),
    default=False,
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
    "--delete-missing",
    is_flag=True,
    help=(
        "Delete DNS record when no IP address found. "
        "Delete A record when IPv4 is missing, AAAA record when IPv6 is missing."
    ),
)
@click.option(
    "--cache-file",
    help="Cache file",
    type=click.Path(dir_okay=False, writable=True, readable=True, path_type=Path),
    default=XDG_CACHE_HOME / "cloudflare-dyndns" / "ip.cache",
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
    proxied: bool,
    ipv4: bool,
    ipv6: bool,
    delete_missing: bool,
    cache_file: Path,
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

    cache_manager = CacheManager(cache_file, force)
    old_cache, new_cache = cache_manager.load()

    cf = CloudFlareWrapper(api_token)

    exit_codes = set()
    ip_methods = [(get_ipv4, old_cache.ipv4, new_cache.ipv4, "A")] if ipv4 else []
    ip_methods += [(get_ipv6, old_cache.ipv6, new_cache.ipv6, "AAAA")] if ipv6 else []

    for ip_func, old_ipcache, new_ipcache, record_type in ip_methods:
        exit_code = handle_update(
            ip_func,
            delete_missing,
            record_type,
            cf,
            domains,
            force,
            old_ipcache,
            new_ipcache,
            debug,
            proxied,
        )
        exit_codes.add(exit_code)

    click.echo()
    if not new_cache.is_empty() and new_cache != old_cache:
        cache_manager.save(new_cache)
    click.echo()

    exit_codes.discard(0)
    if not exit_codes:
        printer.success("Done.")
        return

    final_exit_code = min(exit_codes)
    printer.warning("There were some errors during update.")
    ctx.exit(final_exit_code)


def handle_update(
    get_ip_func: Callable,
    delete_missing: bool,
    record_type: RecordType,
    cf: CloudFlareWrapper,
    domains: List[str],
    force: bool,
    old_cache: IPCache,
    new_cache: IPCache,
    debug: bool,
    proxied: bool,
):
    click.echo()
    try:
        current_ip = get_ip_func()
    except IPServiceError as e:
        printer.error(str(e))
        if not delete_missing:
            return 3

        for domain in domains:
            cf.delete_record(domain, record_type)
        # when the --delete-missing flag is specified, this is the expected behavior
        # so there should be no error reported
        return 0

    if current_ip != old_cache.address:
        new_cache.address = current_ip

    domains_to_update = get_domains(domains, force, current_ip, old_cache, proxied)
    if not domains_to_update:
        return 0

    try:
        success = update_domains(
            cf, domains_to_update, old_cache, new_cache, current_ip, proxied
        )
    except CloudFlareError as e:
        printer.error(str(e))
        if debug:
            raise
        return 2

    except Exception as e:
        printer.error(f"Unknown error: {e}")
        if debug:
            raise
        return 1

    if not success:
        return 2

    return 0


if __name__ == "__main__":
    main()
