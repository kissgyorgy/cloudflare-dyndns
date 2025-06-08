package main

import (
	"fmt"
	"os"
)

const (
	ColorReset  = "\033[0m"
	ColorRed    = "\033[31m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
)

func Success(message string) {
	fmt.Printf("%s%s%s\n", ColorGreen, message, ColorReset)
}

func Warning(message string) {
	fmt.Printf("%s%s%s\n", ColorYellow, message, ColorReset)
}

func Error(message string) {
	fmt.Fprintf(os.Stderr, "%s%s%s\n", ColorRed, message, ColorReset)
}

func Info(message string) {
	fmt.Println(message)
}
