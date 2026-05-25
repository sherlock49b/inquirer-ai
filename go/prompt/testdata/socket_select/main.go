package main

import (
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	defer prompt.ResetSocketTransport()

	lang, err := prompt.Select(prompt.SelectConfig{
		Message: "Language?",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "Python", Value: "Python"},
			prompt.Choice{Name: "Go", Value: "Go"},
			prompt.Choice{Name: "Rust", Value: "Rust"},
		},
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "RESULT:%v\n", lang)
}
