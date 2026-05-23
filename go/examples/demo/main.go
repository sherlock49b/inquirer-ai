package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	fmt.Println("\n  project-init (Go) v0.1.0")
	fmt.Println("  Interactive project scaffolding")
	fmt.Println()

	name, err := prompt.Text(prompt.TextConfig{
		Message: "Project name",
		Validate: func(s string) error {
			if s == "" {
				return fmt.Errorf("project name cannot be empty")
			}
			return nil
		},
	})
	if err != nil {
		fatal(err)
	}

	template, err := prompt.Select(prompt.SelectConfig{
		Message: "Project template",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "Web API (FastAPI)", Value: "web-api", Description: "Python, FastAPI, PostgreSQL"},
			prompt.Choice{Name: "CLI Tool (Click)", Value: "cli-tool", Description: "Python, Click, Rich"},
			prompt.Choice{Name: "gRPC Service", Value: "grpc", Description: "Go, gRPC, Protobuf"},
		},
	})
	if err != nil {
		fatal(err)
	}

	license, err := prompt.Select(prompt.SelectConfig{
		Message: "License",
		Default: "MIT",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "MIT License", Value: "MIT"},
			prompt.Choice{Name: "Apache License 2.0", Value: "Apache-2.0"},
			prompt.Choice{Name: "GNU GPLv3", Value: "GPL-3.0"},
		},
	})
	if err != nil {
		fatal(err)
	}

	features, err := prompt.Checkbox(prompt.CheckboxConfig{
		Message: "Features to include",
		Default: []string{"Docker support"},
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "Docker support", Value: "docker"},
			prompt.Choice{Name: "CI/CD", Value: "ci"},
			prompt.Separator{Text: "── Testing ──"},
			prompt.Choice{Name: "Unit tests", Value: "unit-tests"},
			prompt.Choice{Name: "Load testing", Value: "load-test", Disabled: "coming soon"},
		},
	})
	if err != nil {
		fatal(err)
	}

	proceed, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: "Continue with setup?",
		Default: true,
	})
	if err != nil {
		fatal(err)
	}

	if !proceed {
		fmt.Println("Aborted.")
		return
	}

	port := 8080.0
	portVal, err := prompt.Number(prompt.NumberConfig{
		Message:      "Dev server port",
		Default:      &port,
		Min:          floatPtr(1024),
		Max:          floatPtr(65535),
		FloatAllowed: false,
	})
	if err != nil {
		fatal(err)
	}

	config := map[string]any{
		"project":  name,
		"template": template,
		"license":  license,
		"features": features,
		"port":     portVal,
	}
	data, _ := json.MarshalIndent(config, "", "  ")
	fmt.Println(string(data))
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "Error: %v\n", err)
	os.Exit(1)
}

func floatPtr(v float64) *float64 {
	return &v
}
