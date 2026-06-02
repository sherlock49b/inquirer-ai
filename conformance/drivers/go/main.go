// Conformance driver (Go) for inquirer-ai.
//
// Runs the 11-prompt conformance scenario through the REAL inquirer-ai Go
// library in STDIO AGENT MODE (INQUIRER_AI_MODE=agent,
// INQUIRER_AI_TRANSPORT=stdio). The library reads answers from stdin and
// writes the JSONL protocol (handshake + prompts + validation_errors) to
// stdout. This driver collects each prompt's RETURN VALUE and writes them as a
// single JSON array to the file path given in os.Args[1] (the results file).
//
// Protocol stays on stdout; results go to the file.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func floatPtr(v float64) *float64 { return &v }

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "driver error: %v\n", err)
	os.Exit(1)
}

func main() {
	defer prompt.Cleanup()

	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: driver <results_file>")
		os.Exit(2)
	}
	resultsPath := os.Args[1]

	results := make([]any, 0, 11)

	// P1 text/input — message "Name", default "anon".
	p1, err := prompt.Text(prompt.TextConfig{
		Message: "Name",
		Default: "anon",
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p1)

	// P2 confirm — message "Proceed?", default true.
	p2, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: "Proceed?",
		Default: true,
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p2)

	// P3 number — message "Count", default 10, min 1, max 1000, no floats.
	p3, err := prompt.Number(prompt.NumberConfig{
		Message:      "Count",
		Default:      floatPtr(10),
		Min:          floatPtr(1),
		Max:          floatPtr(1000),
		FloatAllowed: false,
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p3)

	// P4 select — message "Lang".
	p4, err := prompt.Select(prompt.SelectConfig{
		Message: "Lang",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "Python", Value: "py"},
			prompt.Choice{Name: "Go", Value: "go"},
			prompt.Separator{Text: "--"},
			prompt.Choice{Name: "Rust", Value: "rs", Disabled: "soon"},
		},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p4)

	// P5 checkbox — message "Feat", default ["a"].
	p5, err := prompt.Checkbox(prompt.CheckboxConfig{
		Message: "Feat",
		Default: []string{"a"},
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "A", Value: "a"},
			prompt.Choice{Name: "B", Value: "b"},
			prompt.Choice{Name: "C", Value: "c"},
		},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p5)

	// P6 rawlist — message "Ver".
	p6, err := prompt.Rawlist(prompt.RawlistConfig{
		Message: "Ver",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "3.13", Value: "313"},
			prompt.Separator{Text: "-"},
			prompt.Choice{Name: "3.12", Value: "312", Disabled: true},
			prompt.Choice{Name: "3.11", Value: "311"},
		},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p6)

	// P7 search — message "Pkg". Go's Search uses a Source func; return the
	// static choice list regardless of the search term.
	p7, err := prompt.Search(prompt.SearchConfig{
		Message: "Pkg",
		Source: func(_ string) []prompt.ChoiceItem {
			return []prompt.ChoiceItem{
				prompt.Choice{Name: "requests", Value: "req"},
				prompt.Choice{Name: "httpx", Value: "hx"},
			}
		},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p7)

	// P8 password — message "Token", default "def".
	p8, err := prompt.Password(prompt.PasswordConfig{
		Message: "Token",
		Default: "def",
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p8)

	// P9 expand — message "Conflict". Key "Y" is uppercase ON PURPOSE; the
	// library lowercases it to "y".
	p9, err := prompt.Expand(prompt.ExpandConfig{
		Message: "Conflict",
		Choices: []prompt.ExpandChoice{
			{Key: "Y", Name: "Yes", Value: "yes"},
			{Key: "n", Name: "No", Value: "no"},
		},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p9)

	// P10 autocomplete — message "Free", unconstrained.
	p10, err := prompt.Autocomplete(prompt.AutocompleteConfig{
		Message: "Free",
		Choices: []string{"Python", "Go"},
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p10)

	// P11 path — message "Dir", default ".".
	p11, err := prompt.Path(prompt.PathConfig{
		Message: "Dir",
		Default: ".",
	})
	if err != nil {
		fatal(err)
	}
	results = append(results, p11)

	// Write the results array to the results file (NOT stdout — stdout carries
	// the protocol).
	data, err := json.Marshal(results)
	if err != nil {
		fatal(err)
	}
	if err := os.WriteFile(resultsPath, data, 0o644); err != nil {
		fatal(err)
	}
}
