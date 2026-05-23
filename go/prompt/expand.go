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
	Message string
	Choices []ExpandChoice
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
		return expandAgent(cfg)
	}
	return expandTerminal(cfg)
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
	if err := AgentSend(payload); err != nil {
		return nil, err
	}
	answer, err := AgentReceive()
	if err != nil {
		return nil, err
	}
	s := toString(answer)
	lower := strings.ToLower(s)
	for _, c := range cfg.Choices {
		if lower == strings.ToLower(c.Key) || s == toString(c.Value) || s == c.Name {
			return c.Value, nil
		}
	}
	return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, s)
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
