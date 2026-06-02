package prompt

import (
	"fmt"
	"math"
	"regexp"
	"strconv"
	"strings"
)

// numberGrammar is the strict numeric-string grammar shared across all
// language implementations: optional sign, required integer part, optional
// fraction, optional exponent. It rejects "1_000", "3abc", "0x10", ".5",
// "5.", "", "+", and accepts "1e3", "  5  " (after trim), "3.5", "-2", "1E-3".
var numberGrammar = regexp.MustCompile(`^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$`)

// NumberConfig configures a numeric input prompt with optional bounds.
type NumberConfig struct {
	Message      string
	Default      *float64
	Min          *float64
	Max          *float64
	Step         *float64
	FloatAllowed bool
	KeepInput    *bool
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
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return 0, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	if cfg.Filter != nil {
		result = cfg.Filter(result)
	}
	return result, nil
}

func numberAgent(cfg NumberConfig) (float64, error) {
	payload := map[string]any{
		"type":          "number",
		"message":       cfg.Message,
		"default":       cfg.Default,
		"min":           cfg.Min,
		"max":           cfg.Max,
		"num_step":      cfg.Step,
		"float_allowed": cfg.FloatAllowed,
	}
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		result, err := validateNumber(answer, cfg)
		if err != nil {
			return nil, err
		}
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				return nil, fmt.Errorf("%w: %v", ErrValidation, err)
			}
		}
		if cfg.Filter != nil {
			result = cfg.Filter(result)
		}
		return result, nil
	})
	if err != nil {
		return 0, err
	}
	val, ok := raw.(float64)
	if !ok {
		return 0, fmt.Errorf("%w: expected float64, got %T", ErrValidation, raw)
	}
	return val, nil
}

func numberKeepInput(cfg NumberConfig) bool {
	if cfg.KeepInput != nil {
		return *cfg.KeepInput
	}
	return true // default true
}

func numberTerminal(cfg NumberConfig) (float64, error) {
	t := DefaultTheme
	scanner := getTerminalScanner()
	keepInput := numberKeepInput(cfg)
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
			if keepInput {
				parsed, parseErr := strconv.ParseFloat(raw, 64)
				if parseErr == nil {
					cfg.Default = &parsed
				}
			}
			continue
		}
		fmt.Printf("%s %s %g\n", t.SymSuccess, cfg.Message, result)
		return result, nil
	}
}

// isASCIISpace reports whether r is an ASCII whitespace character (space, tab,
// newline, carriage return, vertical tab, form feed).
func isASCIISpace(r rune) bool {
	switch r {
	case ' ', '\t', '\n', '\r', '\v', '\f':
		return true
	default:
		return false
	}
}

func validateNumber(v any, cfg NumberConfig) (float64, error) {
	var num float64
	switch val := v.(type) {
	case float64:
		if math.IsNaN(val) || math.IsInf(val, 0) {
			return 0, fmt.Errorf("%w: Not a valid number", ErrValidation)
		}
		num = val
	case int:
		num = float64(val)
	case string:
		// Trim leading/trailing ASCII whitespace, then the remainder MUST
		// fully match the numeric grammar before parsing.
		trimmed := strings.TrimFunc(val, isASCIISpace)
		if !numberGrammar.MatchString(trimmed) {
			return 0, fmt.Errorf("%w: Not a valid number: %q", ErrValidation, val)
		}
		parsed, err := strconv.ParseFloat(trimmed, 64)
		if err != nil || math.IsNaN(parsed) || math.IsInf(parsed, 0) {
			return 0, fmt.Errorf("%w: Not a valid number: %q", ErrValidation, val)
		}
		num = parsed
	case nil:
		if cfg.Default != nil {
			return *cfg.Default, nil
		}
		return 0, fmt.Errorf("%w: Expected a number, got nil", ErrValidation)
	default:
		return 0, fmt.Errorf("%w: Expected a number, got %T", ErrValidation, v)
	}

	if !cfg.FloatAllowed && num != math.Trunc(num) {
		return 0, fmt.Errorf("%w: Decimal numbers are not allowed", ErrValidation)
	}
	if cfg.Min != nil && num < *cfg.Min {
		return 0, fmt.Errorf("%w: must be at least %g", ErrValidation, *cfg.Min)
	}
	if cfg.Max != nil && num > *cfg.Max {
		return 0, fmt.Errorf("%w: must be at most %g", ErrValidation, *cfg.Max)
	}
	if cfg.Step != nil {
		base := 0.0
		if cfg.Min != nil {
			base = *cfg.Min
		}
		remainder := math.Mod(num-base, *cfg.Step)
		if math.Abs(remainder) > 1e-9 && math.Abs(remainder-*cfg.Step) > 1e-9 {
			return 0, fmt.Errorf("%w: must be a multiple of %v (from %v)", ErrValidation, *cfg.Step, base)
		}
	}
	return num, nil
}
