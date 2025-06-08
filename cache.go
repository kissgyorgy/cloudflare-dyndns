package main

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"path/filepath"
)

type ZoneRecord struct {
	ZoneID   string `json:"zone_id"`
	RecordID string `json:"record_id"`
	Proxied  bool   `json:"proxied"`
}

type IPCache struct {
	Address        *net.IP               `json:"address,omitempty"`
	UpdatedDomains map[string]ZoneRecord `json:"updated_domains"`
}

func NewIPCache() *IPCache {
	return &IPCache{
		UpdatedDomains: make(map[string]ZoneRecord),
	}
}

func (c *IPCache) Clear() {
	c.Address = nil
	c.UpdatedDomains = make(map[string]ZoneRecord)
}

type Cache struct {
	IPv4 *IPCache `json:"ipv4"`
	IPv6 *IPCache `json:"ipv6"`
}

func NewCache() *Cache {
	return &Cache{
		IPv4: NewIPCache(),
		IPv6: NewIPCache(),
	}
}

func (c *Cache) IsEmpty() bool {
	return len(c.IPv4.UpdatedDomains) == 0 && len(c.IPv6.UpdatedDomains) == 0 &&
		c.IPv4.Address == nil && c.IPv6.Address == nil
}

type CacheManager struct {
	path  string
	force bool
	debug bool
}

func NewCacheManager(cachePath string, force bool, debug bool) *CacheManager {
	return &CacheManager{
		path:  cachePath,
		force: force,
		debug: debug,
	}
}

func (cm *CacheManager) ensurePath() error {
	if cm.debug {
		Info(fmt.Sprintf("Creating cache directory: %s", cm.path))
	}
	dir := filepath.Dir(cm.path)
	return os.MkdirAll(dir, 0755)
}

func (cm *CacheManager) Load() (*Cache, *Cache, error) {
	newCache := NewCache()

	if cm.force {
		Warning("Forced update, ignoring cache")
		return NewCache(), newCache, nil
	}

	oldCache, err := cm.load()
	if err != nil {
		cm.Delete()
		return NewCache(), newCache, nil
	}

	return oldCache, newCache, nil
}

func (cm *CacheManager) load() (*Cache, error) {
	Info(fmt.Sprintf("Loading cache from: %s", cm.path))

	data, err := os.ReadFile(cm.path)
	if err != nil {
		if os.IsNotExist(err) {
			Info("Cache file not found.")
			return NewCache(), nil
		}
		return nil, fmt.Errorf("failed to read cache file: %w", err)
	}

	var cache Cache
	if err := json.Unmarshal(data, &cache); err != nil {
		message := "Invalid cache file"
		if cm.debug {
			message += fmt.Sprintf(": %s", string(data))
		}
		Warning(message)
		return nil, fmt.Errorf("invalid cache format: %w", err)
	}

	if cm.debug {
		cacheJSON, _ := json.MarshalIndent(cache, "", "  ")
		Info(fmt.Sprintf("Loaded cache: %s", string(cacheJSON)))
	}

	return &cache, nil
}

func (cm *CacheManager) Save(cache *Cache) error {
	cacheJSON, err := json.MarshalIndent(cache, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal cache: %w", err)
	}

	if cm.debug {
		Info(fmt.Sprintf("Saving cache: %s", string(cacheJSON)))
	}

	Info(fmt.Sprintf("Saving cache to: %s", cm.path))

	if err := cm.ensurePath(); err != nil {
		return fmt.Errorf("failed to create cache directory: %w", err)
	}

	return os.WriteFile(cm.path, cacheJSON, 0644)
}

func (cm *CacheManager) Delete() {
	Warning(fmt.Sprintf("Deleting cache at: %s", cm.path))
	os.Remove(cm.path)
}
