package main

import (
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	defer prompt.ResetSocketTransport()

	port, err := prompt.Number(prompt.NumberConfig{
		Message: "Port?",
		Min:     floatPtr(1024),
		Max:     floatPtr(65535),
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "RESULT:%g\n", port)
}

func floatPtr(v float64) *float64 {
	return &v
}
