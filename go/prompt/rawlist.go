package prompt

import (
	"fmt"
	"strconv"
)

// RawlistConfig configures a numbered list selection prompt.
type RawlistConfig struct {
	Message  string
	Choices  []ChoiceItem
	Validate func(any) error
	Filter   func(any) any
}

// Rawlist prompts the user to select by typing a number index.
func Rawlist(cfg RawlistConfig) (any, error) {
	choices := parseChoices(cfg.Choices)
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}

	var result any
	var err error
	if IsAgentMode() {
		result, err = rawlistAgent(cfg, choices, selectable)
	} else {
		result, err = rawlistTerminal(cfg, choices, selectable)
	}
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func rawlistAgent(cfg RawlistConfig, choices []resolvedChoice, selectable []int) (any, error) {
	payload := map[string]any{
		"type":    "rawlist",
		"message": cfg.Message,
		"choices": marshalItems(cfg.Choices),
	}
	if err := AgentSend(payload); err != nil {
		return nil, err
	}
	answer, err := AgentReceive()
	if err != nil {
		return nil, err
	}

	if num, ok := answer.(float64); ok {
		idx := int(num)
		if idx >= 1 && idx <= len(selectable) {
			return choices[selectable[idx-1]].value, nil
		}
	}

	s := toString(answer)
	for _, idx := range selectable {
		c := choices[idx]
		if s == toString(c.value) || s == c.name {
			return c.value, nil
		}
	}
	return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, toString(answer))
}

func rawlistTerminal(cfg RawlistConfig, choices []resolvedChoice, selectable []int) (any, error) {
	t := DefaultTheme
	for i, idx := range selectable {
		fmt.Printf("  %d) %s\n", i+1, choices[idx].name)
	}

	scanner := getTerminalScanner()
	for {
		fmt.Printf("%s %s: ", t.SymQuestion, cfg.Message)
		if !scanner.Scan() {
			return nil, ErrAborted
		}
		raw := scanner.Text()
		idx, err := strconv.Atoi(raw)
		if err == nil && idx >= 1 && idx <= len(selectable) {
			c := choices[selectable[idx-1]]
			fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, c.name)
			return c.value, nil
		}
		fmt.Printf("  Please enter a number between 1 and %d\n", len(selectable))
	}
}
