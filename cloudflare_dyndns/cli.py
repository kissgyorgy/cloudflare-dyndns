#!/usr/bin/env python3
import os
from typing import List, Optional
import click
import CloudFlare
from .cache import RecordCache, InvalidCache
from .cloudflare import CloudFlareError, CloudFlareWrapper
from .types import IPv4or6Address
from .ip_services import IPServiceError, get_ip, IPV4_SERVICES


def get_domains(
    domains: List[str], force: bool, current_ip: IPv4or6Address, cache: RecordCache,
):
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


def update_domains(
    cf: CloudFlareWrapper,
    domains: List[str],
    cache: RecordCache,
    current_ip: IPv4or6Address,
):
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
    domains_env = os.environ.get("CLOUDFLARE_DOMAINS")
    domains = parse_domains_args(domains, domains_env)

    try:
        current_ip = get_ip(IPV4_SERVICES)
    except IPServiceError:
        click.secho(IPServiceError.__doc__, fg="red")
        ctx.exit(1)

    cache = RecordCache(cache_file, debug)
    cf = CloudFlareWrapper(api_token)

    try:
        if not force:
            try:
                cache.load()
            except InvalidCache:
                click.secho("Invalid cache file, deleting", fg="yellow")
                cache.delete()

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
