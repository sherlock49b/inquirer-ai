package prompt

import (
	"fmt"
)

// AutocompleteConfig configures a text input prompt with suggestion completions.
type AutocompleteConfig struct {
	Message  string
	Choices  []string
	Default  string
	Validate func(string) error
}

// Autocomplete prompts for text input with auto-completion suggestions.
// Accepts any string, not constrained to the suggestion list.
func Autocomplete(cfg AutocompleteConfig) (string, error) {
	if IsAgentMode() {
		return autocompleteAgent(cfg)
	}
	return autocompleteTerminal(cfg)
}

func autocompleteAgent(cfg AutocompleteConfig) (string, error) {
	choiceItems := make([]map[string]any, len(cfg.Choices))
	for i, c := range cfg.Choices {
		choiceItems[i] = map[string]any{"name": c, "value": c}
	}
	payload := map[string]any{
		"type":    "autocomplete",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
		"choices": choiceItems,
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
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return "", fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func autocompleteTerminal(cfg AutocompleteConfig) (string, error) {
	t := DefaultTheme
	scanner := getTerminalScanner()
	for {
		suffix := ""
		if cfg.Default != "" {
			suffix = fmt.Sprintf(" (%s)", cfg.Default)
		}
		fmt.Printf("%s %s%s: ", t.SymQuestion, cfg.Message, suffix)
		if !scanner.Scan() {
			return "", ErrAborted
		}
		result := scanner.Text()
		if result == "" && cfg.Default != "" {
			result = cfg.Default
		}
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				fmt.Printf("  %s\n", err)
				continue
			}
		}
		fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, result)
		return result, nil
	}
}
