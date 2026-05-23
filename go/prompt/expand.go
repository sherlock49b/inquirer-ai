package prompt

import (
	"fmt"
	"strings"
)

// ExpandChoice represents a single option in an expand prompt, identified by a key character.
type ExpandChoice struct {
	Key   string
	Name  string
	Value any
}

// ExpandConfig configures a compact key-based selection prompt.
type ExpandConfig struct {
	Message  string
	Choices  []ExpandChoice
	Validate func(any) error
	Filter   func(any) any
}

// Expand prompts the user to select by typing a single key character.
func Expand(cfg ExpandConfig) (any, error) {
	if len(cfg.Choices) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}
	seen := make(map[string]bool)
	for _, c := range cfg.Choices {
		k := strings.ToLower(c.Key)
		if seen[k] {
			return nil, fmt.Errorf("%w: duplicate expand key: %q", ErrInvalidChoice, k)
		}
		seen[k] = true
	}

	if IsAgentMode() {
		// expandAgent handles validation, filter, and retry internally
		return expandAgent(cfg)
	}
	result, err := expandTerminal(cfg)
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func expandAgent(cfg ExpandConfig) (any, error) {
	items := make([]map[string]any, len(cfg.Choices))
	for i, c := range cfg.Choices {
		items[i] = map[string]any{"key": strings.ToLower(c.Key), "name": c.Name, "value": c.Value}
	}
	payload := map[string]any{
		"type":    "expand",
		"message": cfg.Message,
		"choices": items,
	}
	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		s := toString(answer)
		lower := strings.ToLower(s)
		var matched any
		found := false
		for _, c := range cfg.Choices {
			if lower == strings.ToLower(c.Key) || s == toString(c.Value) || s == c.Name {
				matched = c.Value
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, s)
		}
		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

func expandTerminal(cfg ExpandConfig) (any, error) {
	t := DefaultTheme
	keys := make([]string, len(cfg.Choices))
	for i, c := range cfg.Choices {
		keys[i] = strings.ToLower(c.Key)
	}
	hint := strings.Join(keys, "/")
	scanner := getTerminalScanner()

	for {
		fmt.Printf("%s %s (%s): ", t.SymQuestion, cfg.Message, hint)
		if !scanner.Scan() {
			return nil, ErrAborted
		}
		input := strings.TrimSpace(strings.ToLower(scanner.Text()))
		if input == "h" || input == "help" {
			for _, c := range cfg.Choices {
				fmt.Printf("  %s) %s\n", strings.ToLower(c.Key), c.Name)
			}
			continue
		}
		for _, c := range cfg.Choices {
			if input == strings.ToLower(c.Key) {
				fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, c.Name)
				return c.Value, nil
			}
		}
		fmt.Println("  Invalid key. Press h for help.")
	}
}
