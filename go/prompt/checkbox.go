package prompt

import "fmt"

// CheckboxConfig configures a multi-select checkbox prompt.
type CheckboxConfig struct {
	Message  string
	Choices  []ChoiceItem
	Default  []string
	PageSize int
	Validate func(any) error
	Filter   func(any) any
}

// Checkbox prompts the user to select multiple items from a list.
func Checkbox(cfg CheckboxConfig) ([]any, error) {
	if cfg.PageSize == 0 {
		cfg.PageSize = 10
	}
	choices := parseChoices(cfg.Choices)
	if len(choices) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}
	var result []any
	var err error
	if IsAgentMode() {
		result, err = checkboxAgent(cfg, choices)
	} else {
		result, err = checkboxTerminal(cfg, choices)
	}
	if err != nil {
		return nil, err
	}
	return applyCallbacksList(result, cfg.Validate, cfg.Filter)
}

func checkboxAgent(cfg CheckboxConfig, choices []resolvedChoice) ([]any, error) {
	payload := map[string]any{
		"type":    "checkbox",
		"message": cfg.Message,
		"default": cfg.Default,
		"choices": marshalItems(cfg.Choices),
	}
	if err := AgentSend(payload); err != nil {
		return nil, err
	}

	answer, err := AgentReceive()
	if err != nil {
		return nil, err
	}

	list, ok := answer.([]any)
	if !ok {
		return nil, fmt.Errorf("%w: expected a list", ErrValidation)
	}

	var result []any
	for _, v := range list {
		s := toString(v)
		found := false
		for _, c := range choices {
			if !c.selectable {
				continue
			}
			if s == toString(c.value) || s == c.name {
				result = append(result, c.value)
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, s)
		}
	}
	return result, nil
}

func checkboxTerminal(cfg CheckboxConfig, choices []resolvedChoice) ([]any, error) {
	t := DefaultTheme
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: no selectable choices", ErrInvalidChoice)
	}

	cursor := selectable[0]
	checked := make(map[int]bool)
	for _, idx := range selectable {
		for _, d := range cfg.Default {
			c := choices[idx]
			if c.name == d || toString(c.value) == d {
				checked[idx] = true
			}
		}
	}

	for {
		fmt.Printf("\033[2J\033[H")
		fmt.Printf("%s %s\n", t.SymQuestion, cfg.Message)
		start, end := visibleRange(cursor, len(choices), cfg.PageSize)
		if start > 0 {
			fmt.Println("  (more above)")
		}
		for i := start; i < end; i++ {
			c := choices[i]
			if c.isSeparator {
				fmt.Printf("  %s\n", c.name)
				continue
			}
			if !c.selectable {
				fmt.Printf("  %s %s (disabled)\n", t.SymUnchecked, c.name)
				continue
			}
			arrow := " "
			if i == cursor {
				arrow = t.SymPointer
			}
			mark := t.SymUnchecked
			if checked[i] {
				mark = t.SymChecked
			}
			fmt.Printf("%s %s %s\n", arrow, mark, c.name)
		}
		if end < len(choices) {
			fmt.Println("  (more below)")
		}

		key, err := readKey()
		if err != nil {
			return nil, ErrAborted
		}
		switch key {
		case keyUp:
			cursor = moveCursor(cursor, -1, selectable, true)
		case keyDown:
			cursor = moveCursor(cursor, 1, selectable, true)
		case keySpace:
			checked[cursor] = !checked[cursor]
		case keyEnter:
			var result []any
			for _, idx := range selectable {
				if checked[idx] {
					result = append(result, choices[idx].value)
				}
			}
			fmt.Printf("\033[2J\033[H%s %s\n", t.SymSuccess, cfg.Message)
			return result, nil
		case keyCtrlC:
			return nil, ErrAborted
		}
	}
}
