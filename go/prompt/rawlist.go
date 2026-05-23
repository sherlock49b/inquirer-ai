package prompt

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
)

type RawlistConfig struct {
	Message string
	Choices []ChoiceItem
}

func Rawlist(cfg RawlistConfig) (any, error) {
	choices := parseChoices(cfg.Choices)
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}

	if IsAgentMode() {
		return rawlistAgent(cfg, choices, selectable)
	}
	return rawlistTerminal(cfg, choices, selectable)
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

	scanner := bufio.NewScanner(os.Stdin)
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
