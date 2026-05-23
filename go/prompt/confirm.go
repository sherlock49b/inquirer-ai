package prompt

import (
	"fmt"
	"strings"
)

// ConfirmConfig configures a yes/no confirmation prompt.
type ConfirmConfig struct {
	Message  string
	Default  bool
	Validate func(any) error
	Filter   func(any) any
}

// Confirm prompts for a yes/no answer.
func Confirm(cfg ConfirmConfig) (bool, error) {
	var result bool
	var err error
	if IsAgentMode() {
		result, err = confirmAgent(cfg)
	} else {
		result, err = confirmTerminal(cfg)
	}
	if err != nil {
		return false, err
	}
	if cfg.Filter != nil {
		if v, ok := cfg.Filter(result).(bool); ok {
			result = v
		}
	}
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return false, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func confirmAgent(cfg ConfirmConfig) (bool, error) {
	payload := map[string]any{
		"type":    "confirm",
		"message": cfg.Message,
		"default": cfg.Default,
	}
	if err := AgentSend(payload); err != nil {
		return false, err
	}

	answer, err := AgentReceive()
	if err != nil {
		return false, err
	}
	return toBool(answer), nil
}

func confirmTerminal(cfg ConfirmConfig) (bool, error) {
	t := DefaultTheme
	hint := "y/N"
	if cfg.Default {
		hint = "Y/n"
	}

	scanner := getTerminalScanner()
	for {
		fmt.Printf("%s %s (%s): ", t.SymQuestion, cfg.Message, hint)
		if !scanner.Scan() {
			return false, ErrAborted
		}
		input := strings.TrimSpace(strings.ToLower(scanner.Text()))
		if input == "" {
			fmt.Printf("%s %s %v\n", t.SymSuccess, cfg.Message, boolDisplay(cfg.Default))
			return cfg.Default, nil
		}
		if input == "y" || input == "yes" {
			fmt.Printf("%s %s Yes\n", t.SymSuccess, cfg.Message)
			return true, nil
		}
		if input == "n" || input == "no" {
			fmt.Printf("%s %s No\n", t.SymSuccess, cfg.Message)
			return false, nil
		}
		fmt.Println("  Invalid input. Please enter y or n.")
	}
}

func toBool(v any) bool {
	switch val := v.(type) {
	case bool:
		return val
	case string:
		lower := strings.ToLower(val)
		return lower == "y" || lower == "yes" || lower == "true" || lower == "1"
	case float64:
		return val != 0
	default:
		return false
	}
}

func boolDisplay(v bool) string {
	if v {
		return "Yes"
	}
	return "No"
}
