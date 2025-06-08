package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
)

type CloudFlareError struct {
	Message string
}

func (e CloudFlareError) Error() string {
	return e.Message
}

type CloudFlareTokenInvalid struct {
	Message string
}

func (e CloudFlareTokenInvalid) Error() string {
	return e.Message
}

type CloudFlareResponse struct {
	Result interface{} `json:"result"`
	Errors []struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"errors"`
	Success bool `json:"success"`
}

type Zone struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type DNSRecord struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Name    string `json:"name"`
	Content string `json:"content"`
	Proxied bool   `json:"proxied"`
	TTL     int    `json:"ttl"`
}

type CloudFlareWrapper struct {
	apiToken string
	client   *http.Client
	baseURL  string
	zones    []Zone
}

func NewCloudFlareWrapper(apiToken string) *CloudFlareWrapper {
	return &CloudFlareWrapper{
		apiToken: apiToken,
		client:   &http.Client{},
		baseURL:  "https://api.cloudflare.com/client/v4",
	}
}

func (cf *CloudFlareWrapper) request(method, path string, body interface{}, params map[string]string) (interface{}, error) {
	var bodyReader io.Reader
	if body != nil {
		bodyBytes, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(bodyBytes)
	}

	reqURL := cf.baseURL + path
	if len(params) > 0 {
		u, _ := url.Parse(reqURL)
		q := u.Query()
		for k, v := range params {
			q.Set(k, v)
		}
		u.RawQuery = q.Encode()
		reqURL = u.String()
	}

	req, err := http.NewRequest(method, reqURL, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+cf.apiToken)
	req.Header.Set("Content-Type", "application/json")

	resp, err := cf.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var cfResp CloudFlareResponse
	if err := json.Unmarshal(respBody, &cfResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		Error(fmt.Sprintf("CloudFlare API Client error: %v\nMaybe your API token is invalid?", cfResp.Errors))
		return nil, CloudFlareError{Message: "Client error"}
	}

	if len(cfResp.Errors) > 0 {
		Error(fmt.Sprintf("CloudFlare API error: %v", cfResp.Errors))
		return nil, CloudFlareError{Message: "API error"}
	}

	return cfResp.Result, nil
}

func (cf *CloudFlareWrapper) VerifyToken() error {
	req, err := http.NewRequest("GET", cf.baseURL+"/user/tokens/verify", nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+cf.apiToken)

	resp, err := cf.client.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return CloudFlareTokenInvalid{Message: "Invalid API token"}
	} else if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		var cfResp CloudFlareResponse
		json.Unmarshal(body, &cfResp)
		return CloudFlareError{Message: fmt.Sprintf("%v", cfResp.Errors)}
	}

	return nil
}

func (cf *CloudFlareWrapper) GetAllZoneIDs() ([]Zone, error) {
	if cf.zones != nil {
		return cf.zones, nil
	}

	result, err := cf.request("GET", "/zones", nil, nil)
	if err != nil {
		return nil, err
	}

	zonesData, err := json.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal zones: %w", err)
	}

	var zones []Zone
	if err := json.Unmarshal(zonesData, &zones); err != nil {
		return nil, fmt.Errorf("failed to unmarshal zones: %w", err)
	}

	cf.zones = zones
	return zones, nil
}

func (cf *CloudFlareWrapper) GetZoneID(domain string) (string, error) {
	zones, err := cf.GetAllZoneIDs()
	if err != nil {
		return "", err
	}

	for _, zone := range zones {
		if len(domain) >= len(zone.Name) && domain[len(domain)-len(zone.Name):] == zone.Name {
			return zone.ID, nil
		}
	}

	Error(fmt.Sprintf("Cannot find domain \"%s\" at CloudFlare", domain))
	return "", CloudFlareError{Message: "Domain not found"}
}

func (cf *CloudFlareWrapper) getRecords(domain string) ([]DNSRecord, error) {
	zoneID, err := cf.GetZoneID(domain)
	if err != nil {
		return nil, err
	}

	params := map[string]string{"name": domain}
	result, err := cf.request("GET", fmt.Sprintf("/zones/%s/dns_records", zoneID), nil, params)
	if err != nil {
		return nil, err
	}

	recordsData, err := json.Marshal(result)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal records: %w", err)
	}

	var records []DNSRecord
	if err := json.Unmarshal(recordsData, &records); err != nil {
		return nil, fmt.Errorf("failed to unmarshal records: %w", err)
	}

	return records, nil
}

func (cf *CloudFlareWrapper) GetRecordID(domain string, recordType RecordType) (string, error) {
	records, err := cf.getRecords(domain)
	if err != nil {
		return "", err
	}

	for _, record := range records {
		if record.Type == string(recordType) && record.Name == domain {
			return record.ID, nil
		}
	}

	Info(fmt.Sprintf("Failed to get domain records for \"%s\"", domain))
	return "", CloudFlareError{Message: fmt.Sprintf("Cannot find %s record for %s", recordType, domain)}
}

func (cf *CloudFlareWrapper) CreateRecord(domain string, ip net.IP, proxied bool) (string, error) {
	zoneID, err := cf.GetZoneID(domain)
	if err != nil {
		return "", err
	}

	recordType := GetRecordType(ip)
	Info(fmt.Sprintf("Creating a new %s record for \"%s\".", recordType, domain))

	payload := map[string]interface{}{
		"name":    domain,
		"type":    string(recordType),
		"content": ip.String(),
		"ttl":     1,
		"proxied": proxied,
	}

	result, err := cf.request("POST", fmt.Sprintf("/zones/%s/dns_records", zoneID), payload, nil)
	if err != nil {
		Error(fmt.Sprintf("Failed to create new record for \"%s\": %v", domain, err))
		return "", err
	}

	recordData, err := json.Marshal(result)
	if err != nil {
		return "", fmt.Errorf("failed to marshal record: %w", err)
	}

	var record DNSRecord
	if err := json.Unmarshal(recordData, &record); err != nil {
		return "", fmt.Errorf("failed to unmarshal record: %w", err)
	}

	return record.ID, nil
}

func (cf *CloudFlareWrapper) UpdateRecord(domain string, ip net.IP, zoneID, recordID string, proxied bool) error {
	if zoneID == "" {
		var err error
		zoneID, err = cf.GetZoneID(domain)
		if err != nil {
			return err
		}
	}

	recordType := GetRecordType(ip)
	if recordID == "" {
		var err error
		recordID, err = cf.GetRecordID(domain, recordType)
		if err != nil {
			return err
		}
	}

	Info(fmt.Sprintf("Updating \"%s\" %s record.", domain, recordType))

	payload := map[string]interface{}{
		"name":    domain,
		"type":    string(recordType),
		"content": ip.String(),
		"proxied": proxied,
	}

	_, err := cf.request("PUT", fmt.Sprintf("/zones/%s/dns_records/%s", zoneID, recordID), payload, nil)
	if err != nil {
		Error(fmt.Sprintf("Failed to update domain \"%s\": %v", domain, err))
		return err
	}

	return nil
}

func (cf *CloudFlareWrapper) DeleteRecord(domain string, recordType RecordType) error {
	Warning(fmt.Sprintf("Deleting %s record for \"%s\".", recordType, domain))

	zoneID, err := cf.GetZoneID(domain)
	if err != nil {
		return err
	}

	recordID, err := cf.GetRecordID(domain, recordType)
	if err != nil {
		Info(fmt.Sprintf("%s record for \"%s\" doesn't exist.", recordType, domain))
		return nil
	}

	_, err = cf.request("DELETE", fmt.Sprintf("/zones/%s/dns_records/%s", zoneID, recordID), nil, nil)
	return err
}
