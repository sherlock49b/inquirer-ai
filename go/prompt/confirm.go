package prompt

import (
	"fmt"
	"math"
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
	if IsAgentMode() {
		// confirmAgent handles filter, validate, and retry internally
		return confirmAgent(cfg)
	}
	result, err := confirmTerminal(cfg)
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
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		result := toBool(answer)
		if cfg.Filter != nil {
			if v, ok := cfg.Filter(result).(bool); ok {
				result = v
			}
		}
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				return nil, fmt.Errorf("%w: %v", ErrValidation, err)
			}
		}
		return result, nil
	})
	if err != nil {
		return false, err
	}
	val, ok := raw.(bool)
	if !ok {
		return false, fmt.Errorf("%w: expected bool, got %T", ErrValidation, raw)
	}
	return val, nil
}

func confirmTerminal(cfg ConfirmConfig) (bool, error) {
	hint := "y/N"
	if cfg.Default {
		hint = "Y/n"
	}

	scanner := getTerminalScanner()
	for {
		fmt.Printf("%s %s: ", renderQuestion(cfg.Message), styleMuted.Render("("+hint+")"))
		if !scanner.Scan() {
			return false, ErrAborted
		}
		input := strings.TrimSpace(strings.ToLower(scanner.Text()))
		if input == "" {
			fmt.Println(renderSuccess(cfg.Message, boolDisplay(cfg.Default)))
			return cfg.Default, nil
		}
		if input == "y" || input == "yes" {
			fmt.Println(renderSuccess(cfg.Message, "Yes"))
			return true, nil
		}
		if input == "n" || input == "no" {
			fmt.Println(renderSuccess(cfg.Message, "No"))
			return false, nil
		}
		fmt.Println(renderError("Invalid input. Please enter y or n."))
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
		return !math.IsNaN(val) && !math.IsInf(val, 0) && val != 0
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
