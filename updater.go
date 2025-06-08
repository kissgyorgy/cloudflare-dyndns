package main

import (
	"fmt"
	"net"
	"strings"
)

type CFUpdater struct {
	domains       []string
	cf            *CloudFlareWrapper
	oldCache      *Cache
	newCache      *Cache
	force         bool
	deleteMissing bool
	proxied       bool
	debug         bool
}

func NewCFUpdater(domains []string, cf *CloudFlareWrapper, oldCache, newCache *Cache,
	force, deleteMissing, proxied, debug bool) *CFUpdater {
	return &CFUpdater{
		domains:       domains,
		cf:            cf,
		oldCache:      oldCache,
		newCache:      newCache,
		force:         force,
		deleteMissing: deleteMissing,
		proxied:       proxied,
		debug:         debug,
	}
}

func (u *CFUpdater) UpdateIPv4() ExitCode {
	return u.handleUpdate(GetIPv4, RecordTypeA, u.oldCache.IPv4, u.newCache.IPv4)
}

func (u *CFUpdater) UpdateIPv6() ExitCode {
	return u.handleUpdate(GetIPv6, RecordTypeAAAA, u.oldCache.IPv6, u.newCache.IPv6)
}

type GetIPFunc func([]IPService) (net.IP, error)

func (u *CFUpdater) handleUpdate(getIPFunc GetIPFunc, recordType RecordType,
	oldCache, newCache *IPCache) ExitCode {

	fmt.Println()

	currentIP, err := getIPFunc(nil)
	if err != nil {
		Error(err.Error())
		if !u.deleteMissing {
			return ExitCodeIPServiceError
		}

		for _, domain := range u.domains {
			u.cf.DeleteRecord(domain, recordType)
		}
		return ExitCodeOK
	}

	if oldCache.Address == nil || !currentIP.Equal(*oldCache.Address) {
		newCache.Address = &currentIP
	}

	domainsToUpdate := u.getDomains(currentIP, oldCache)
	if len(domainsToUpdate) == 0 {
		return ExitCodeOK
	}

	updateSuccess := u.updateDomains(domainsToUpdate, currentIP, oldCache, newCache)
	if !updateSuccess {
		return ExitCodeCloudflareError
	}

	return ExitCodeOK
}

func (u *CFUpdater) getDomains(currentIP net.IP, oldCache *IPCache) []string {
	if oldCache.Address == nil || !currentIP.Equal(*oldCache.Address) {
		return u.domains
	}

	updatedDomains := make(map[string]bool)
	for domain, zoneRecord := range oldCache.UpdatedDomains {
		if zoneRecord.Proxied == u.proxied {
			updatedDomains[domain] = true
		}
	}

	if len(updatedDomains) > 0 {
		domainList := make([]string, 0, len(updatedDomains))
		for domain := range updatedDomains {
			domainList = append(domainList, domain)
		}
		Success(fmt.Sprintf("Domains with this IP address in cache: %s", strings.Join(domainList, ", ")))
	} else {
		Info("There are no domains with this IP in cache.")
	}

	var missingDomains []string
	for _, domain := range u.domains {
		if !updatedDomains[domain] {
			missingDomains = append(missingDomains, domain)
		}
	}

	if len(missingDomains) == 0 {
		Success(fmt.Sprintf("Every domain is up-to-date for %s.", currentIP.String()))
		return []string{}
	}

	return missingDomains
}

func (u *CFUpdater) updateDomains(domains []string, currentIP net.IP, oldCache, newCache *IPCache) bool {
	success := true

	for _, domain := range domains {
		zoneID, recordID, err := u.updateDomain(domain, currentIP, oldCache)
		if err != nil {
			success = false
			Error(fmt.Sprintf("Failed to update records for domain \"%s\"", domain))
			if u.debug {
				Error(err.Error())
			}
			continue
		}

		zoneRecord := ZoneRecord{
			ZoneID:   zoneID,
			RecordID: recordID,
			Proxied:  u.proxied,
		}
		newCache.UpdatedDomains[domain] = zoneRecord
	}

	return success
}

func (u *CFUpdater) updateDomain(domain string, currentIP net.IP, oldCache *IPCache) (string, string, error) {
	cacheRecord, exists := oldCache.UpdatedDomains[domain]
	updateRecordFailed := false

	var zoneID, recordID string

	if exists {
		zoneID = cacheRecord.ZoneID
		recordID = cacheRecord.RecordID
		err := u.cf.UpdateRecord(domain, currentIP, zoneID, recordID, u.proxied)
		if err != nil {
			updateRecordFailed = true
		}
	}

	if !exists || updateRecordFailed {
		var err error
		zoneID, err = u.cf.GetZoneID(domain)
		if err != nil {
			return "", "", err
		}

		recordID, err = u.cf.GetRecordID(domain, GetRecordType(currentIP))
		if err != nil {
			recordID, err = u.cf.CreateRecord(domain, currentIP, u.proxied)
			if err != nil {
				return "", "", err
			}
		} else {
			err = u.cf.UpdateRecord(domain, currentIP, zoneID, recordID, u.proxied)
			if err != nil {
				return "", "", err
			}
		}
	}

	return zoneID, recordID, nil
}
