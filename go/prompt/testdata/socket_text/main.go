package main

import (
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	defer prompt.ResetSocketTransport()

	name, err := prompt.Text(prompt.TextConfig{
		Message: "Name?",
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "RESULT:%s\n", name)
}
