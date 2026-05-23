package prompt

import (
	"bufio"
	"fmt"
	"os"
)

// TextConfig configures a free-text input prompt.
type TextConfig struct {
	Message  string
	Default  string
	Validate func(string) error
	Filter   func(string) string
}

// Text prompts for a single line of text input.
func Text(cfg TextConfig) (string, error) {
	if IsAgentMode() {
		return textAgent(cfg)
	}
	return textTerminal(cfg)
}

func textAgent(cfg TextConfig) (string, error) {
	payload := map[string]any{
		"type":    "input",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
	}
	if err := AgentSend(payload); err != nil {
		return "", err
	}

	answer, err := AgentReceive()
	if err != nil {
		return "", err
	}

	result := toString(answer)
	if result == "" && cfg.Default != "" {
		result = cfg.Default
	}
	return applyTextCallbacks(result, cfg)
}

func textTerminal(cfg TextConfig) (string, error) {
	t := DefaultTheme
	for {
		suffix := ""
		if cfg.Default != "" {
			suffix = fmt.Sprintf(" (%s)", cfg.Default)
		}
		fmt.Printf("%s %s%s: ", t.SymQuestion, cfg.Message, suffix)

		scanner := bufio.NewScanner(os.Stdin)
		if !scanner.Scan() {
			return "", ErrAborted
		}
		result := scanner.Text()
		if result == "" && cfg.Default != "" {
			result = cfg.Default
		}

		final, err := applyTextCallbacks(result, cfg)
		if err != nil {
			fmt.Printf("  %s\n", err)
			continue
		}
		fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, final)
		return final, nil
	}
}

func applyTextCallbacks(result string, cfg TextConfig) (string, error) {
	if cfg.Filter != nil {
		result = cfg.Filter(result)
	}
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return "", fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
