#!/usr/bin/env python3
import os
from pathlib import Path
from typing import List, Optional

import click

from cloudflare_dyndns.updater import CFUpdater

from . import printer
from .cache import CacheManager
from .cloudflare import CloudFlareWrapper

cache_path = os.environ.get("XDG_CACHE_HOME", "~/.cache")
XDG_CACHE_HOME = Path(cache_path).expanduser()


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
    updater = CFUpdater(
        domains, cf, old_cache, new_cache, force, delete_missing, proxied, debug
    )

    exit_codes = set()

    if ipv4:
        exit_code = updater.update_ipv4()
        exit_codes.add(exit_code)
    if ipv6:
        exit_code = updater.update_ipv6()
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


if __name__ == "__main__":
    main()
