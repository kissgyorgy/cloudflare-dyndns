package main

import (
	"net"
)

type RecordType string

const (
	RecordTypeA    RecordType = "A"
	RecordTypeAAAA RecordType = "AAAA"
)

type ExitCode int

const (
	ExitCodeOK              ExitCode = 0
	ExitCodeUnknownError    ExitCode = 1
	ExitCodeIPServiceError  ExitCode = 2
	ExitCodeCloudflareError ExitCode = 3
)

func GetRecordType(ip net.IP) RecordType {
	if ip.To4() != nil {
		return RecordTypeA
	}
	return RecordTypeAAAA
}
