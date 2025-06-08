package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const version = "6.0.0"

func main() {
	var (
		apiToken      = flag.String("api-token", os.Getenv("CLOUDFLARE_API_TOKEN"), "CloudFlare API Token")
		apiTokenFile  = flag.String("api-token-file", os.Getenv("CLOUDFLARE_API_TOKEN_FILE"), "File containing CloudFlare API Token")
		verifyToken   = flag.Bool("verify-token", false, "Check if the API token is valid through the CloudFlare API")
		proxied       = flag.Bool("proxied", false, "Whether the records are receiving the performance and security benefits of Cloudflare")
		ipv4          = flag.Bool("4", true, "Turn on IPv4 detection and set A records")
		noIPv4        = flag.Bool("no-4", false, "Turn off IPv4 detection")
		ipv6          = flag.Bool("6", false, "Turn on IPv6 detection and set AAAA records")
		noIPv6        = flag.Bool("no-6", false, "Turn off IPv6 detection")
		deleteMissing = flag.Bool("delete-missing", false, "Delete DNS record when no IP address found")
		cacheFile     = flag.String("cache-file", getDefaultCacheFile(), "Cache file")
		force         = flag.Bool("force", false, "Delete cache and update every domain")
		debug         = flag.Bool("debug", false, "More verbose messages and Exception tracebacks")
		showVersion   = flag.Bool("version", false, "Show the version and exit")
		showHelp      = flag.Bool("help", false, "Show this message and exit")
	)

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [OPTIONS] [DOMAINS]...\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "A command line script to update CloudFlare DNS A and/or AAAA records\n")
		fmt.Fprintf(os.Stderr, "based on the current IP address(es) of the machine running the script.\n\n")
		fmt.Fprintf(os.Stderr, "For the main domain (the \"@\" record), simply put \"example.com\".\n")
		fmt.Fprintf(os.Stderr, "Subdomains can also be specified, eg. \"*.example.com\" or \"sub.example.com\"\n\n")
		fmt.Fprintf(os.Stderr, "You can set the list of domains to update in the CLOUDFLARE_DOMAINS\n")
		fmt.Fprintf(os.Stderr, "environment variable, in which the domains has to be separated by\n")
		fmt.Fprintf(os.Stderr, "whitespace, so don't forget to quote the value!\n\n")
		fmt.Fprintf(os.Stderr, "The script supports both IPv4 and IPv6 addresses. The default is to set only\n")
		fmt.Fprintf(os.Stderr, "A records for IPv4, which you can change with the relevant options.\n\n")
		fmt.Fprintf(os.Stderr, "Options:\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nShell exit codes:\n")
		fmt.Fprintf(os.Stderr, "  1: Unknown error happened\n")
		fmt.Fprintf(os.Stderr, "  2: IP cannot be determined (IP service error)\n")
		fmt.Fprintf(os.Stderr, "  3: CloudFlare related error (cannot call API, cannot get records, etc...)\n")
	}

	flag.Parse()

	if *showHelp {
		flag.Usage()
		os.Exit(0)
	}

	if *showVersion {
		fmt.Printf("cloudflare-dyndns version %s\n", version)
		os.Exit(0)
	}

	// Handle IPv4/IPv6 flags
	if *noIPv4 {
		*ipv4 = false
	}
	if *noIPv6 {
		*ipv6 = false
	}

	if !*ipv4 && !*ipv6 {
		Error("You have to specify at least one IP mode; use -4 or -6.")
		os.Exit(int(ExitCodeUnknownError))
	}

	// Parse API token
	apiTokenValue, err := parseAPITokenArgs(*apiToken, *apiTokenFile)
	if err != nil {
		Error(err.Error())
		os.Exit(int(ExitCodeUnknownError))
	}

	cf := NewCloudFlareWrapper(apiTokenValue)

	if *verifyToken {
		verifyAPIToken(cf)
		return
	}

	// Parse domains
	domains, err := parseDomainsArgs(flag.Args(), os.Getenv("CLOUDFLARE_DOMAINS"))
	if err != nil {
		Error(err.Error())
		os.Exit(int(ExitCodeUnknownError))
	}

	// Initialize cache
	cacheManager := NewCacheManager(*cacheFile, *force, *debug)
	oldCache, newCache, err := cacheManager.Load()
	if err != nil {
		Error(fmt.Sprintf("Failed to load cache: %v", err))
		os.Exit(int(ExitCodeUnknownError))
	}

	// Create updater
	updater := NewCFUpdater(domains, cf, oldCache, newCache, *force, *deleteMissing, *proxied, *debug)

	var exitCodes []ExitCode

	if *ipv4 {
		exitCode := updater.UpdateIPv4()
		exitCodes = append(exitCodes, exitCode)
	}

	if *ipv6 {
		exitCode := updater.UpdateIPv6()
		exitCodes = append(exitCodes, exitCode)
	}

	fmt.Println()

	// Handle exit codes
	finalExitCode := ExitCodeOK
	for _, code := range exitCodes {
		if code != ExitCodeOK {
			finalExitCode = code
			break
		}
	}

	if finalExitCode != ExitCodeOK {
		Warning("There were errors during update.")
		cacheManager.Delete()
		os.Exit(int(finalExitCode))
	}

	// Save cache if needed
	if !newCache.IsEmpty() && !cacheEquals(newCache, oldCache) {
		if err := cacheManager.Save(newCache); err != nil {
			Error(fmt.Sprintf("Failed to save cache: %v", err))
		}
	}

	Success("Done.")
	os.Exit(int(ExitCodeOK))
}

func getDefaultCacheFile() string {
	cacheDir := os.Getenv("XDG_CACHE_HOME")
	if cacheDir == "" {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "./ip.cache"
		}
		cacheDir = filepath.Join(homeDir, ".cache")
	}
	return filepath.Join(cacheDir, "cloudflare-dyndns", "ip.cache")
}

func parseDomainsArgs(domains []string, domainsEnv string) ([]string, error) {
	if len(domains) == 0 && domainsEnv == "" {
		return nil, fmt.Errorf("You need to specify either domains argument or CLOUDFLARE_DOMAINS environment variable!")
	}

	if len(domains) > 0 && domainsEnv != "" {
		return nil, fmt.Errorf("Ambiguous domain list, use either argument list or CLOUDFLARE_DOMAINS environment variable, not both!")
	}

	if domainsEnv != "" {
		domains = strings.Fields(domainsEnv)
	}

	Info("Domains to update: " + strings.Join(domains, ", "))
	return domains, nil
}

func parseAPITokenArgs(apiToken, apiTokenFile string) (string, error) {
	if apiToken != "" && apiTokenFile != "" {
		return "", fmt.Errorf("Ambiguous api token, use either --api-token or --api-token-file, not both!")
	}

	if apiToken != "" {
		return apiToken, nil
	}

	if apiTokenFile != "" {
		data, err := os.ReadFile(apiTokenFile)
		if err != nil {
			return "", fmt.Errorf("failed to read API token file: %w", err)
		}
		return strings.TrimSpace(string(data)), nil
	}

	return "", fmt.Errorf("You have to specify an api token; use --api-token or --api-token-file.")
}

func verifyAPIToken(cf *CloudFlareWrapper) {
	err := cf.VerifyToken()
	if err != nil {
		if _, ok := err.(CloudFlareTokenInvalid); ok {
			Error("CloudFlare API Token is invalid!")
			os.Exit(int(ExitCodeCloudflareError))
		}
		Error(fmt.Sprintf("Failed to verify CloudFlare API Token for other reason: %v", err))
		os.Exit(int(ExitCodeCloudflareError))
	}

	Success("CloudFlare API Token is valid for managing the following zones:")
	zones, err := cf.GetAllZoneIDs()
	if err != nil {
		Error(fmt.Sprintf("Failed to get zones: %v", err))
		os.Exit(int(ExitCodeCloudflareError))
	}

	for _, zone := range zones {
		Info(fmt.Sprintf("  - %s", zone.Name))
	}
	os.Exit(int(ExitCodeOK))
}

func cacheEquals(cache1, cache2 *Cache) bool {
	// Simple comparison - in a real implementation you might want a more sophisticated comparison
	if cache1.IPv4.Address == nil && cache2.IPv4.Address != nil {
		return false
	}
	if cache1.IPv4.Address != nil && cache2.IPv4.Address == nil {
		return false
	}
	if cache1.IPv4.Address != nil && cache2.IPv4.Address != nil && !cache1.IPv4.Address.Equal(*cache2.IPv4.Address) {
		return false
	}

	if cache1.IPv6.Address == nil && cache2.IPv6.Address != nil {
		return false
	}
	if cache1.IPv6.Address != nil && cache2.IPv6.Address == nil {
		return false
	}
	if cache1.IPv6.Address != nil && cache2.IPv6.Address != nil && !cache1.IPv6.Address.Equal(*cache2.IPv6.Address) {
		return false
	}

	if len(cache1.IPv4.UpdatedDomains) != len(cache2.IPv4.UpdatedDomains) {
		return false
	}
	if len(cache1.IPv6.UpdatedDomains) != len(cache2.IPv6.UpdatedDomains) {
		return false
	}

	for k, v1 := range cache1.IPv4.UpdatedDomains {
		if v2, ok := cache2.IPv4.UpdatedDomains[k]; !ok || v1 != v2 {
			return false
		}
	}

	for k, v1 := range cache1.IPv6.UpdatedDomains {
		if v2, ok := cache2.IPv6.UpdatedDomains[k]; !ok || v1 != v2 {
			return false
		}
	}

	return true
}
