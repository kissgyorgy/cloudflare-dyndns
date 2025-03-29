from typing import Callable, Iterable, List

import click

from . import printer
from .cache import Cache, IPCache, ZoneRecord
from .cloudflare import CloudFlareError, CloudFlareWrapper
from .ip_services import IPServiceError, get_ipv4, get_ipv6
from .types import ExitCode, IPAddress, RecordType, get_record_type


class CFUpdater:
    def __init__(
        self,
        domains: List[str],
        cf: CloudFlareWrapper,
        old_cache: Cache,
        new_cache: Cache,
        force: bool,
        delete_missing: bool,
        proxied: bool,
        debug: bool,
    ):
        self._domains = domains
        self._cf = cf
        self._old_cache = old_cache
        self._new_cache = new_cache
        self._force = force
        self._delete_missing = delete_missing
        self._proxied = proxied
        self._debug = debug
        self._exit_codes = set()

    def update_ipv4(self):
        return self._handle_update(
            get_ipv4, "A", self._old_cache.ipv4, self._new_cache.ipv4
        )

    def update_ipv6(self):
        return self._handle_update(
            get_ipv6, "AAAA", self._old_cache.ipv6, self._new_cache.ipv6
        )

    def _handle_update(
        self,
        get_ip_func: Callable,
        record_type: RecordType,
        old_cache: IPCache,
        new_cache: IPCache,
    ) -> int:
        click.echo()
        try:
            current_ip = get_ip_func()
        except IPServiceError as e:
            printer.error(str(e))
            if not self._delete_missing:
                return ExitCode.IP_SERVICE_ERROR

            for domain in self._domains:
                self._cf.delete_record(domain, record_type)
            # when the --delete-missing flag is specified, this is the expected behavior
            # so there should be no error reported
            return ExitCode.OK

        if current_ip != old_cache.address:
            new_cache.address = current_ip

        if not (domains_to_update := self._get_domains(current_ip, old_cache)):
            return ExitCode.OK

        try:
            update_success = self._update_domains(
                domains_to_update, current_ip, old_cache, new_cache
            )
        except CloudFlareError as e:
            printer.error(str(e))
            if self._debug:
                raise
            return ExitCode.CLOUDFLARE_ERROR

        except Exception as e:
            printer.error(f"Unknown error: {e}")
            if self._debug:
                raise
            return ExitCode.UNKNOWN_ERROR

        if not update_success:
            return ExitCode.CLOUDFLARE_ERROR

        return ExitCode.OK

    def _get_domains(self, current_ip: IPAddress, old_cache: IPCache) -> Iterable[str]:
        if current_ip != old_cache.address:
            return self._domains

        updated_domains = {
            d
            for d, zone_record in old_cache.updated_domains.items()
            if zone_record.proxied is self._proxied
        }

        updated_domains_list = ", ".join(updated_domains)
        if updated_domains:
            printer.success(
                f"Domains with this IP address in cache: {updated_domains_list}"
            )
        else:
            printer.info("There are no domains with this IP in cache.")

        missing_domains = set(self._domains) - updated_domains
        if not missing_domains:
            printer.success(f"Every domain is up-to-date for {current_ip}.")
            return []
        else:
            return missing_domains

    def _update_domains(
        self,
        domains: Iterable[str],
        current_ip: IPAddress,
        old_cache: IPCache,
        new_cache: IPCache,
    ):
        success = True

        for domain in domains:
            try:
                zone_id, record_id = self._update_domain(domain, current_ip, old_cache)
            except CloudFlareError:
                success = False
                printer.error(f'Failed to update records for domain "{domain}"')
                continue

            zone_record = ZoneRecord(
                zone_id=zone_id, record_id=record_id, proxied=self._proxied
            )
            new_cache.updated_domains[domain] = zone_record

        return success

    def _update_domain(
        self, domain: str, current_ip: IPAddress, old_cache: IPCache
    ) -> tuple[str, str]:
        cache_record = old_cache.updated_domains.get(domain)
        update_record_failed = False

        if cache_record is not None:
            zone_id = cache_record.zone_id
            record_id = cache_record.record_id
            try:
                self._cf.update_record(
                    domain, current_ip, zone_id, record_id, self._proxied
                )
            except CloudFlareError:
                update_record_failed = True

        if cache_record is None or update_record_failed:
            zone_id = self._cf.get_zone_id(domain)

            try:
                record_id = self._cf.get_record_id(domain, get_record_type(current_ip))
            except CloudFlareError:
                record_id = self._cf.create_record(domain, current_ip, self._proxied)
            else:
                self._cf.update_record(
                    domain, current_ip, zone_id, record_id, self._proxied
                )

        return zone_id, record_id
