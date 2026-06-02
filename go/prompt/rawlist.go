package prompt

import (
	"fmt"
	"math"
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

	if IsAgentMode() {
		// rawlistAgent handles validation, filter, and retry internally
		return rawlistAgent(cfg, choices, selectable)
	}
	result, err := rawlistTerminal(cfg, choices, selectable)
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func rawlistAgent(cfg RawlistConfig, choices []resolvedChoice, selectable []int) (any, error) {
	payload := map[string]any{
		"type":    "rawlist",
		"message": cfg.Message,
		"default": nil,
		"choices": selectablePayload(choices, selectable),
	}
	validValues := make([]any, 0, len(selectable))
	for _, idx := range selectable {
		validValues = append(validValues, choices[idx].value)
	}

	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		var matched any
		found := false

		// A JSON number must be a 1-based integer index over the selectable
		// list. A non-integer number (e.g. 1.5) is rejected, not truncated.
		if num, ok := answer.(float64); ok {
			if num != math.Trunc(num) {
				return nil, newValidationError(ErrInvalidChoice, invalidChoiceMessage(answer, validValues))
			}
			idx := int(num)
			if idx >= 1 && idx <= len(selectable) {
				matched = choices[selectable[idx-1]].value
				found = true
			} else {
				return nil, newValidationError(ErrInvalidChoice, invalidChoiceMessage(answer, validValues))
			}
		}

		// Otherwise match by value (type-aware) or name over the selectable list.
		if !found {
			for _, idx := range selectable {
				c := choices[idx]
				if matchesChoice(answer, c) {
					matched = c.value
					found = true
					break
				}
			}
		}

		if !found {
			return nil, newValidationError(ErrInvalidChoice, invalidChoiceMessage(answer, validValues))
		}

		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

// selectablePayload builds the agent payload "choices" list for prompts that
// advertise only the selectable (non-separator, non-disabled) items, numbered
// implicitly 1..n by their order. Used by rawlist per the parity contract.
func selectablePayload(choices []resolvedChoice, selectable []int) []any {
	result := make([]any, 0, len(selectable))
	for _, idx := range selectable {
		c := choices[idx]
		result = append(result, map[string]any{"name": c.name, "value": c.value})
	}
	return result
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
