package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"
)

type IPServiceError struct {
	Message string
}

func (e IPServiceError) Error() string {
	return e.Message
}

type ResponseParser func(string) string

func StripWhitespace(response string) string {
	return strings.TrimSpace(response)
}

type IPService struct {
	Name           string
	URL            string
	ResponseParser ResponseParser
}

var IPv4Services = []IPService{
	{"ipify API", "https://api.ipify.org", StripWhitespace},
	{"AWS check ip", "https://checkip.amazonaws.com/", StripWhitespace},
	{"major.io icanhazip", "https://ipv4.icanhazip.com/", StripWhitespace},
	{"Namecheap DynamicDNS", "https://dynamicdns.park-your-domain.com/getip", StripWhitespace},
}

var IPv6Services = []IPService{
	{"ipify API", "https://api6.ipify.org", StripWhitespace},
	{"ip.tyk.nu", "https://ip.tyk.nu/", StripWhitespace},
	{"wgetip.com", "https://wgetip.com/", StripWhitespace},
	{"major.io icanhazip", "https://ipv6.icanhazip.com/", StripWhitespace},
}

func getIP(client *http.Client, services []IPService, version string) (net.IP, error) {
	for _, service := range services {
		Info(fmt.Sprintf("Checking current IPv%s address with service: %s (%s)", version, service.Name, service.URL))

		resp, err := client.Get(service.URL)
		if err != nil {
			Info(fmt.Sprintf("Service %s unreachable, skipping.", service.URL))
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			Info(fmt.Sprintf("Service returned error status: %d, skipping.", resp.StatusCode))
			continue
		}

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			Info(fmt.Sprintf("Failed to read response from %s, skipping.", service.URL))
			continue
		}

		ipStr := service.ResponseParser(string(body))
		ip := net.ParseIP(ipStr)
		if ip == nil {
			Warning(fmt.Sprintf("Service returned invalid IP Address: %s, skipping.", ipStr))
			continue
		}

		Info(fmt.Sprintf("Current IP address: %s", ip.String()))
		return ip, nil
	}

	return nil, IPServiceError{
		Message: "Tried all IP Services, but couldn't determine current IP address.",
	}
}

func GetIPv4(services []IPService) (net.IP, error) {
	if len(services) == 0 {
		services = IPv4Services
	}

	dialer := &net.Dialer{
		LocalAddr: &net.TCPAddr{
			IP: net.ParseIP("0.0.0.0"),
		},
		Timeout: 30 * time.Second,
	}

	transport := &http.Transport{
		DialContext: dialer.DialContext,
	}

	client := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}

	ipv4, err := getIP(client, services, "4")
	if err != nil {
		return nil, err
	}

	if ipv4.To4() == nil {
		return nil, IPServiceError{
			Message: "IP Service returned IPv6 address instead of IPv4.\nThere is a bug with the IP Service.",
		}
	}

	return ipv4, nil
}

func GetIPv6(services []IPService) (net.IP, error) {
	if len(services) == 0 {
		services = IPv6Services
	}

	dialer := &net.Dialer{
		LocalAddr: &net.TCPAddr{
			IP: net.ParseIP("::"),
		},
		Timeout: 30 * time.Second,
	}

	transport := &http.Transport{
		DialContext: dialer.DialContext,
	}

	client := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}

	ipv6, err := getIP(client, services, "6")
	if err != nil {
		return nil, err
	}

	if ipv6.To4() != nil {
		return nil, IPServiceError{
			Message: "IP Service returned IPv4 address instead of IPv6.\nYou either don't have an IPv6 address, or there is a bug with the IP Service.",
		}
	}

	return ipv6, nil
}
