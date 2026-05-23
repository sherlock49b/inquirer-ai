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
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		payload := map[string]any{
			"type":    "autocomplete",
			"message": cfg.Message,
			"default": nilIfEmpty(cfg.Default),
			"choices": cfg.Choices,
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
				valErr := fmt.Errorf("%w: %v", ErrValidation, err)
				if attempt < maxRetries-1 {
					AgentSendValidationError(valErr.Error())
					continue
				}
				return "", valErr
			}
		}
		return result, nil
	}
	return "", fmt.Errorf("%w: max retries exceeded", ErrValidation)
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
