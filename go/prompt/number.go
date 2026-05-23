package prompt

import (
	"fmt"
	"math"
	"strconv"
)

// NumberConfig configures a numeric input prompt with optional bounds.
type NumberConfig struct {
	Message      string
	Default      *float64
	Min          *float64
	Max          *float64
	FloatAllowed bool
	Validate     func(float64) error
	Filter       func(float64) float64
}

// Number prompts for a numeric value, validating against optional min/max bounds.
func Number(cfg NumberConfig) (float64, error) {
	if IsAgentMode() {
		// numberAgent handles validation, filter, and retry internally
		return numberAgent(cfg)
	}
	result, err := numberTerminal(cfg)
	if err != nil {
		return 0, err
	}
	if cfg.Filter != nil {
		result = cfg.Filter(result)
	}
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return 0, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func numberAgent(cfg NumberConfig) (float64, error) {
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		payload := map[string]any{
			"type":          "number",
			"message":       cfg.Message,
			"default":       cfg.Default,
			"min":           cfg.Min,
			"max":           cfg.Max,
			"float_allowed": cfg.FloatAllowed,
		}
		if err := AgentSend(payload); err != nil {
			return 0, err
		}
		answer, err := AgentReceive()
		if err != nil {
			return 0, err
		}
		result, err := validateNumber(answer, cfg)
		if err != nil {
			if attempt < maxRetries-1 {
				AgentSendValidationError(err.Error())
				continue
			}
			return 0, err
		}
		if cfg.Filter != nil {
			result = cfg.Filter(result)
		}
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				valErr := fmt.Errorf("%w: %v", ErrValidation, err)
				if attempt < maxRetries-1 {
					AgentSendValidationError(valErr.Error())
					continue
				}
				return 0, valErr
			}
		}
		return result, nil
	}
	return 0, fmt.Errorf("%w: max retries exceeded", ErrValidation)
}

func numberTerminal(cfg NumberConfig) (float64, error) {
	t := DefaultTheme
	scanner := getTerminalScanner()
	for {
		suffix := ""
		if cfg.Default != nil {
			suffix = fmt.Sprintf(" (%g)", *cfg.Default)
		}
		fmt.Printf("%s %s%s: ", t.SymQuestion, cfg.Message, suffix)
		if !scanner.Scan() {
			return 0, ErrAborted
		}
		raw := scanner.Text()
		if raw == "" && cfg.Default != nil {
			fmt.Printf("%s %s %g\n", t.SymSuccess, cfg.Message, *cfg.Default)
			return *cfg.Default, nil
		}
		result, err := validateNumber(raw, cfg)
		if err != nil {
			fmt.Printf("  %s\n", err)
			continue
		}
		fmt.Printf("%s %s %g\n", t.SymSuccess, cfg.Message, result)
		return result, nil
	}
}

func validateNumber(v any, cfg NumberConfig) (float64, error) {
	var num float64
	switch val := v.(type) {
	case float64:
		if math.IsNaN(val) || math.IsInf(val, 0) {
			return 0, fmt.Errorf("%w: not a valid number", ErrValidation)
		}
		num = val
	case int:
		num = float64(val)
	case string:
		var err error
		num, err = strconv.ParseFloat(val, 64)
		if err != nil {
			return 0, fmt.Errorf("%w: not a valid number: %q", ErrValidation, val)
		}
		if math.IsNaN(num) || math.IsInf(num, 0) {
			return 0, fmt.Errorf("%w: not a valid number: %q", ErrValidation, val)
		}
	case nil:
		if cfg.Default != nil {
			return *cfg.Default, nil
		}
		return 0, fmt.Errorf("%w: expected a number", ErrValidation)
	default:
		return 0, fmt.Errorf("%w: expected a number, got %T", ErrValidation, v)
	}

	if !cfg.FloatAllowed && num != math.Trunc(num) {
		return 0, fmt.Errorf("%w: decimal numbers are not allowed", ErrValidation)
	}
	if cfg.Min != nil && num < *cfg.Min {
		return 0, fmt.Errorf("%w: must be at least %g", ErrValidation, *cfg.Min)
	}
	if cfg.Max != nil && num > *cfg.Max {
		return 0, fmt.Errorf("%w: must be at most %g", ErrValidation, *cfg.Max)
	}
	return num, nil
}
